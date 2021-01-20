#!/usr/bin/env python3

import os
import re
import time
import json
import signal
import inspect
import argparse
from pick import pick
from urllib3.exceptions import ProtocolError
from pprint import pformat
from kubernetes import client, config, watch
from pygments import highlight
from pygments.lexers import JsonLexer, PythonLexer, TextLexer
from pygments.formatters import Terminal256Formatter
from contextlib import contextmanager
from rich.console import Console
from rich.columns import Columns
from rich.table import Table
from rich import box
from rich.live import Live
from kubernetes.config.config_exception import ConfigException


def jprint(**kwargs):
    """ easy json.dumps indent=4 printer cause im lazyyyy """
    passed_name = list(kwargs.items())[0][0]
    passed_data = kwargs[passed_name]
    ptype = str(type(passed_data))
    print_header = "+---- [{} - {}] --\n".format(passed_name, ptype)
    print_footer = "+------------------"
    print(print_header)
    found = False
    if isinstance(passed_data, dict):
        try:
            pre_color = json.dumps(passed_data, indent=4)
            print(highlight(pre_color, JsonLexer(), Terminal256Formatter()))
            found = True
        except TypeError:
            print(highlight(pformat(passed_data), PythonLexer(), Terminal256Formatter()))
    elif isinstance(passed_data, list):
        pre_color = json.dumps(passed_data, indent=4)
        print(highlight(pre_color, JsonLexer(), Terminal256Formatter()))
        found = True
    elif isinstance(passed_data, str):
        print(highlight(passed_data, TextLexer(), Terminal256Formatter()))
        found = True
    elif isinstance(passed_data, int):
        print(passed_data)
        found = True
    if inspect.getmembers(passed_data, inspect.isclass) and not found:
        print(highlight(pformat(passed_data), PythonLexer(), Terminal256Formatter()))
        print(str(passed_data))
    print(print_footer)


def convert_or_pass(obj):
    """ Allows storing of crappy AWS datestamp """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        json.JSONEncoder.default(self, obj)


class SmartFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)


def ezhighlight(my_filter, msg):
    reset_color = "\x1b[0m"
    matches = re.findall(my_filter, msg)
    for each in matches:
        highlight_color = "\x1b[33m"
        msg = msg.replace(each, f"{highlight_color}{each}{reset_color}")
    return msg


def config_parser():
    """ argparse """
    parser = argparse.ArgumentParser(description="hit ec2 for results", formatter_class=SmartFormatter, epilog="example: ")
    parser.add_argument("-f", required=False, help="R|search event text for REGEX\n\nexample: '(mycontainer|thing)'", default=None)
    parser.add_argument("-c", required=False, help="R|use context", default=None)
    parser.add_argument("-w", action='store_true', required=False, help="R|warnings loglevel only")
    parser.add_argument("-n", action='store_true', required=False, help="R|normal loglevel only")
    return parser


BEAT_TIME = 0.04


@contextmanager
def beat(length: int = 1) -> None:
    with console:
        yield
    time.sleep(length * BEAT_TIME)


if __name__ == "__main__":
    try:
        try:
            config.load_kube_config()
        except ConfigException as e:
            print(e)
            os.kill(os.getpid(), signal.SIGUSR1)
        contexts = config.list_kube_config_contexts()
        context = [context.get('name').split('.')[0] for context in contexts[0]]
        clean_context = []
        for each in context:
            if each not in clean_context:
                clean_context.append(each)
        parser = config_parser()
        args = parser.parse_args()
        my_filter = args.f if args.f is not None else None
        my_context = args.c if args.c is not None else None
        if args.n:
            message_type = "Normal"
        if args.w:
            message_type = "Warning"
        else:
            message_type = None
        if not my_context:
            chosen_context, _ = pick(clean_context, title="Pick the context to load")
        else:
            chosen_context = my_context
        core_client = client.CoreV1Api(api_client=config.new_client_from_config(context=chosen_context))
        w = watch.Watch()
        console = Console()
        table = Table(show_footer=False, show_header=True, expand=True)
        table.row_styles = ["none", "dim"]
        table.add_column("created on", style="cyan", header_style="bold cyan")
        table.add_column("context", style="blue", header_style="bold blue")
        table.add_column("namespace", style="blue", header_style="bold blue")
        table.add_column("name", style="magenta", header_style="bold magenta")
        table.add_column("kind")
        table.add_column("reason", style="green", header_style="bold green")
        table.add_column("type", style="green", header_style="bold green")
        table.add_column("message")
        table_centered = Columns((table,), align="center", expand=True)
        table.box = box.SIMPLE
        console.clear()
        with Live(
            table_centered, console=console, refresh_per_second=10, vertical_overflow="visible"
        ):
            try:
                for event in w.stream(core_client.list_event_for_all_namespaces, _request_timeout=300):
                    action = list(event.values())[0]
                    metadata = event['object'].metadata
                    creation_timestamp = metadata.creation_timestamp
                    creation_ts_human = creation_timestamp.strftime("%Y.%m.%d %H:%M:%S")
                    namespace = metadata.namespace
                    kind = event['object'].involved_object.kind
                    event_type = event['object'].type
                    event_reason = event['object'].reason
                    name = metadata.name.split('.')[0]
                    event_key = creation_timestamp.strftime("%Y-%m-%d %H:%M:%S") + name
                    message = event['object'].message.replace('(', "[").replace(")", "]")
                    context_len = len(chosen_context)
                    if event_type:
                        if my_filter:
                            r = re.compile(f'.*{my_filter}.*')
                            my_list = [name, namespace, message, event_type]
                            matches = list(filter(r.match, my_list))
                            if matches:
                                with beat(10):
                                    table.add_row(
                                        creation_ts_human,
                                        chosen_context,
                                        namespace,
                                        name,
                                        kind,
                                        event_type,
                                        event_reason,
                                        message
                                    )
            except ProtocolError as e:
                print("Web Stream connection broken! Rebuilding")
                print(e)
            pass
    except KeyboardInterrupt:
        os.kill(os.getpid(), signal.SIGUSR1)
