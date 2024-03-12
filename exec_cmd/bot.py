# exec - A maubot plugin to execute code.
# Copyright (C) 2019 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
from typing import Type, Set, Optional, Any, Dict
from io import StringIO
from html import escape as escape_orig
from time import time

from jinja2 import Template

from mautrix.types import EventType, UserID, TextMessageEventContent, MessageType, Format
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from mautrix.util.formatter import MatrixParser, EntityString, SimpleEntity, EntityType
from maubot import Plugin, MessageEvent
from maubot.handlers import event, command

from .runner import PythonRunner, ShellRunner, OutputType


def escape(val: Optional[str]) -> Optional[str]:
    return escape_orig(val) if val is not None else None


class ConfigValidationError(Exception):
    pass


class EntityParser(MatrixParser[EntityString]):
    fs = EntityString[SimpleEntity, EntityType]


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("prefix_exec")
        helper.copy("prefix_cmd")
        helper.copy("userbot")
        helper.copy("whitelist_exec")
        helper.copy("whitelist_cmd")
        helper.copy("output.interval")
        helper.copy("output.template_args")
        helper.copy("output.plaintext")
        helper.copy("output.html")
        helper.copy("commands")


class ExecCmdBot(Plugin):
    whitelist_exec: Set[UserID]
    whitelist_cmd: Set[UserID]
    userbot: bool
    prefix_exec: str
    prefix_cmd: str
    output_interval: int
    plaintext_template: Template
    html_template: Template
    commands: Dict

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    async def start(self) -> None:
        self.on_external_config_update()

    def on_external_config_update(self) -> None:
        self.config.load_and_update()
        self.whitelist_exec = set(self.config["whitelist_exec"])
        self.whitelist_cmd = set(self.config["whitelist_cmd"])
        self.userbot = self.config["userbot"]
        self.prefix_exec = self.config["prefix_exec"]
        self.prefix_cmd = self.config["prefix_cmd"]
        self.output_interval = self.config["output.interval"]
        template_args = self.config["output.template_args"]
        self.plaintext_template = Template(self.config["output.plaintext"], **template_args)
        self.html_template = Template(self.config["output.html"], **template_args)
        self.commands = self.config["commands"]
        if any(" " in cmd for cmd in self.commands):
            raise ConfigValidationError("commands keys contain spaces")

    def format_status(self, code: str, language: str, output: str = "", output_html: str = "",
                      return_value: Any = None, exception_header: Optional[str] = None,
                      exception: Optional[str] = None, duration: Optional[float] = None,
                      msgtype: MessageType = MessageType.NOTICE) -> TextMessageEventContent:
        return_value = repr(return_value) if return_value is not None else None
        content = TextMessageEventContent(
            msgtype=msgtype, format=Format.HTML,
            body=self.plaintext_template.render(
                code=code, language=language, output=output, return_value=return_value,
                duration=duration, exception=exception, exception_header=exception_header),
            formatted_body=self.html_template.render(
                code=escape(code), language=language, output=output_html,
                return_value=escape(return_value), duration=duration, exception=escape(exception),
                exception_header=escape(exception_header)))
        return content

    async def exec_runner(self, evt: MessageEvent, lang: str, code: str, stdin: str = "") -> None:
        if not code or not lang:
            return

        if lang == "python":
            runner = PythonRunner(namespace={
                "client": self.client,
                "event": evt,
            })
        elif lang in ("shell", "bash", "sh"):
            runner = ShellRunner()
        else:
            await evt.respond(f'Unsupported language "{lang}"')
            return

        if self.userbot:
            msgtype = MessageType.TEXT
            content = self.format_status(code, lang, msgtype=msgtype)
            await evt.edit(content)
            output_event_id = evt.event_id
        else:
            msgtype = MessageType.NOTICE
            content = self.format_status(code, lang, msgtype=msgtype)
            output_event_id = await evt.respond(content)

        output = StringIO()
        output_html = StringIO()
        return_value: Any = None
        exception_header, exception = None, None
        start_time = time()
        prev_output = start_time
        async for out_type, data in runner.run(code, stdin):
            if out_type == OutputType.STDOUT:
                output.write(data)
                output_html.write(escape(data))
            elif out_type == OutputType.STDERR:
                output.write(data)
                output_html.write(f'<font color="red" data-mx-color="red">{escape(data)}</font>')
            elif out_type == OutputType.RETURN:
                return_value = data
                continue
            elif out_type == OutputType.EXCEPTION:
                exception_header, exception = runner.format_exception(data)
                continue

            cur_time = time()
            if prev_output + self.output_interval < cur_time:
                content = self.format_status(code, lang, output.getvalue(), output_html.getvalue(),
                                             msgtype=msgtype)
                content.set_edit(output_event_id)
                await self.client.send_message(evt.room_id, content)
                prev_output = cur_time
        duration = time() - start_time
        print(return_value)
        content = self.format_status(code, lang, output.getvalue(), output_html.getvalue(),
                                     return_value, exception_header, exception, duration,
                                     msgtype=msgtype)
        content.set_edit(output_event_id)
        await self.client.send_message(evt.room_id, content)

    @event.on(EventType.ROOM_MESSAGE)
    async def exec(self, evt: MessageEvent) -> None:
        if ((evt.content.msgtype != MessageType.TEXT
             or evt.sender not in self.whitelist_exec
             or not evt.content.body.startswith(self.prefix_exec)
             or not evt.content.formatted_body)):
            return

        command = await EntityParser().parse(evt.content.formatted_body)
        entity: SimpleEntity
        code: Optional[str] = None
        lang: Optional[str] = None
        stdin: str = ""
        for entity in command.entities:
            if entity.type != EntityType.PREFORMATTED:
                continue
            current_lang = entity.extra_info["language"].lower()
            value = command.text[entity.offset:entity.offset + entity.length]
            if not code:
                code = value
                lang = current_lang
            elif current_lang == "stdin" or current_lang == "input":
                stdin += value
        if not code or not lang:
            return

        await self.exec_runner(evt, lang, code, stdin=stdin)

    @command.new(name=lambda self: self.prefix_cmd)
    @command.argument("command", pass_raw=True, required=True)
    async def cmd(self, evt: MessageEvent, command: str) -> None:
        if evt.sender not in self.whitelist_cmd:
            return

        if not command:
            available = ["`" + c.replace("_", " ") + "`" for c in self.commands.keys()]
            available_list = "- " + "\n- ".join(available)
            await evt.reply(f"available commands:\n{available_list}")
            return

        key: str
        key = command.replace(" ", "_")
        if key not in self.commands.keys():
            await evt.reply("unknown command")
            return

        await self.exec_runner(evt, "sh", self.commands[key])
