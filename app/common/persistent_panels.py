from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from logging import getLogger
from typing import Protocol

import discord

from app.common.discord_types import as_text_channel
from app.common.offline import OfflineInfo, build_offline_view, get_emergency_contact_mentions

logger = getLogger(__name__)

PANEL_MARKER_ID_MASK = 0x7FFFFFFF


@dataclass(frozen=True, slots=True)
class PersistentPanelContent:
    embeds: tuple[discord.Embed, ...]
    view: discord.ui.View | discord.ui.LayoutView | None = None


PanelRenderer = Callable[[], Awaitable[PersistentPanelContent]]


@dataclass(slots=True)
class PersistentPanel:
    panel_id: str
    channel_id: int
    render: PanelRenderer
    offline_description: str
    message: discord.Message | None = None


def get_panel_marker_id(panel_id: str) -> int:
    digest = hashlib.blake2s(f"asteroid:persistent-panel:{panel_id}".encode(), digest_size=4).digest()
    marker_id = int.from_bytes(digest, "big") & PANEL_MARKER_ID_MASK
    return marker_id or 1


def mark_layout_view(view: discord.ui.LayoutView, panel_id: str) -> None:
    if not view.children:
        return
    view.children[0].id = get_panel_marker_id(panel_id)


def component_has_marker(component: object, marker_id: int) -> bool:
    if getattr(component, "id", None) == marker_id:
        return True
    for attribute_name in ("children", "components"):
        children = getattr(component, attribute_name, None)
        if children is None:
            continue
        if any(component_has_marker(child, marker_id) for child in children):
            return True
    return False


def message_has_panel_marker(message: discord.Message, panel_id: str) -> bool:
    marker_id = get_panel_marker_id(panel_id)
    components = getattr(message, "components", ())
    return any(component_has_marker(component, marker_id) for component in components)


class PersistentPanelBot(Protocol):
    @property
    def user(self) -> discord.ClientUser | None: ...

    def get_channel(
        self, channel_id: int, /
    ) -> discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel | None: ...

    async def fetch_channel(
        self, channel_id: int, /
    ) -> discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel: ...

    def is_operating_channel(self, channel: object) -> bool: ...

    async def application_info(self) -> discord.AppInfo: ...


class PersistentPanelManager:
    def __init__(self, bot: PersistentPanelBot) -> None:
        self.bot = bot
        self._panels: dict[str, PersistentPanel] = {}
        self._publish_lock = asyncio.Lock()
        self._offline = False

    def register(
        self,
        panel_id: str,
        channel_id: int,
        render: PanelRenderer,
        *,
        offline_description: str,
    ) -> None:
        if panel_id in self._panels:
            raise ValueError(f"パネルは既に登録されています: panel_id={panel_id}")
        self._panels[panel_id] = PersistentPanel(
            panel_id=panel_id,
            channel_id=channel_id,
            render=render,
            offline_description=offline_description,
        )
        logger.debug(f"常駐パネルを登録しました: panel_id={panel_id} channel_id={channel_id}")

    def unregister(self, panel_id: str) -> None:
        self._panels.pop(panel_id, None)

    def get_message(self, panel_id: str) -> discord.Message | None:
        return self._get_panel(panel_id).message

    async def initialize(self, panel_id: str) -> bool:
        panel = self._get_panel(panel_id)
        async with self._publish_lock:
            if self._offline:
                logger.debug(f"オフライン化済みのため常駐パネルの初期化をスキップしました: panel_id={panel_id}")
                return False
            try:
                content = await panel.render()
                return await self._publish(panel, content, reconcile_latest=True)
            except Exception:
                logger.exception(
                    f"常駐パネルの初期化中に予期しないエラーが発生しました: "
                    f"panel_id={panel.panel_id} channel_id={panel.channel_id}"
                )
                return False

    async def refresh(self, panel_id: str) -> bool:
        panel = self._get_panel(panel_id)
        async with self._publish_lock:
            if self._offline:
                logger.debug(f"オフライン化済みのため常駐パネルの更新をスキップしました: panel_id={panel_id}")
                return False
            try:
                content = await panel.render()
                return await self._publish(panel, content, reconcile_latest=panel.message is None)
            except Exception:
                logger.exception(
                    f"常駐パネルの更新中に予期しないエラーが発生しました: "
                    f"panel_id={panel.panel_id} channel_id={panel.channel_id}"
                )
                return False

    async def set_all_offline(self, info: OfflineInfo) -> dict[str, bool]:
        async with self._publish_lock:
            self._offline = True
            try:
                contacts = await get_emergency_contact_mentions(self.bot)
            except Exception:
                logger.exception("緊急連絡先の取得に失敗したため、常駐パネルをオフライン化できませんでした。")
                return dict.fromkeys(self._panels, False)

            results: dict[str, bool] = {}
            updated_at = datetime.now(UTC)
            for panel in self._panels.values():
                try:
                    content = PersistentPanelContent(
                        embeds=(),
                        view=build_offline_view(
                            info,
                            panel.offline_description,
                            contacts,
                            updated_at=updated_at,
                        ),
                    )
                    results[panel.panel_id] = await self._publish(
                        panel,
                        content,
                        reconcile_latest=panel.message is None,
                    )
                except Exception:
                    logger.exception(
                        f"常駐パネルのオフライン化中に予期しないエラーが発生しました: "
                        f"panel_id={panel.panel_id} channel_id={panel.channel_id}"
                    )
                    results[panel.panel_id] = False
            return results

    def _get_panel(self, panel_id: str) -> PersistentPanel:
        try:
            return self._panels[panel_id]
        except KeyError as error:
            raise KeyError(f"未登録の常駐パネルです: panel_id={panel_id}") from error

    async def _publish(
        self,
        panel: PersistentPanel,
        content: PersistentPanelContent,
        *,
        reconcile_latest: bool,
    ) -> bool:
        channel = await self._get_channel(panel)
        if channel is None:
            return False

        if reconcile_latest:
            panel.message = await self._get_reusable_latest_message(panel, channel)

        if isinstance(content.view, discord.ui.LayoutView):
            mark_layout_view(content.view, panel.panel_id)

        if panel.message is None:
            try:
                if isinstance(content.view, discord.ui.LayoutView):
                    message = await channel.send(view=content.view)
                elif content.view is None:
                    message = await channel.send(embeds=list(content.embeds))
                else:
                    message = await channel.send(embeds=list(content.embeds), view=content.view)
            except discord.HTTPException as error:
                logger.warning(
                    f"常駐パネルの送信に失敗しました: panel_id={panel.panel_id} "
                    f"channel_id={panel.channel_id} status={error.status} code={error.code}"
                )
                return False
            panel.message = message
            logger.info(
                f"常駐パネルを送信しました: panel_id={panel.panel_id} "
                f"channel_id={panel.channel_id} message_id={message.id}"
            )
            return True

        try:
            if isinstance(content.view, discord.ui.LayoutView):
                await panel.message.edit(content=None, embeds=[], attachments=[], view=content.view)
            else:
                await panel.message.edit(content=None, embeds=list(content.embeds), view=content.view)
        except discord.NotFound:
            logger.warning(
                f"常駐パネルメッセージが見つからなかったため再作成します: "
                f"panel_id={panel.panel_id} channel_id={panel.channel_id} message_id={panel.message.id}"
            )
            panel.message = None
            return await self._publish(panel, content, reconcile_latest=False)
        except discord.HTTPException as error:
            logger.warning(
                f"常駐パネルの更新に失敗しました: panel_id={panel.panel_id} "
                f"channel_id={panel.channel_id} message_id={panel.message.id} "
                f"status={error.status} code={error.code}"
            )
            return False

        logger.debug(
            f"常駐パネルを更新しました: panel_id={panel.panel_id} "
            f"channel_id={panel.channel_id} message_id={panel.message.id}"
        )
        return True

    async def _get_channel(self, panel: PersistentPanel) -> discord.TextChannel | None:
        if not panel.channel_id:
            logger.warning(f"常駐パネルのチャンネルが設定されていません: panel_id={panel.panel_id}")
            return None

        channel = as_text_channel(self.bot.get_channel(panel.channel_id))
        if channel is None:
            try:
                channel = as_text_channel(await self.bot.fetch_channel(panel.channel_id))
            except discord.HTTPException as error:
                logger.warning(
                    f"常駐パネルのチャンネル取得に失敗しました: panel_id={panel.panel_id} "
                    f"channel_id={panel.channel_id} status={error.status} code={error.code}"
                )
                return None

        if channel is None:
            logger.warning(
                f"常駐パネルの送信先がテキストチャンネルではありません: "
                f"panel_id={panel.panel_id} channel_id={panel.channel_id}"
            )
            return None
        if not self.bot.is_operating_channel(channel):
            logger.warning(
                f"常駐パネルの送信先が稼働ギルド外です: panel_id={panel.panel_id} channel_id={panel.channel_id}"
            )
            return None
        return channel

    async def _get_reusable_latest_message(
        self,
        panel: PersistentPanel,
        channel: discord.TextChannel,
    ) -> discord.Message | None:
        latest_message = None
        async for message in channel.history(limit=1):
            latest_message = message
            break

        bot_user = self.bot.user
        if latest_message is None or bot_user is None or latest_message.author.id != bot_user.id:
            return None
        if not message_has_panel_marker(latest_message, panel.panel_id):
            logger.debug(
                f"最新のBOTメッセージが対象パネルではないため再利用しません: "
                f"panel_id={panel.panel_id} channel_id={channel.id} message_id={latest_message.id}"
            )
            return None
        return latest_message
