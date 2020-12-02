#!/usr/bin/env python3.8


from textwrap import wrap, TextWrapper
from pick import pick
from datetime import datetime
from urllib3.exceptions import ProtocolError
from kubernetes import client, config, watch

import re
import sys
import inspect
import argparse


class SmartFormatter(argparse.HelpFormatter):
    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines()
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width)


def config_parser():
    """ argparse """
    parser = argparse.ArgumentParser(description="hit ec2 for results", formatter_class=SmartFormatter, epilog="example: ")
    parser.add_argument("-f", required=False, help="R|search event text for WORD\n\nexample: mycontainer", default=None)
    parser.add_argument("-w", action='store_true', required=False, help="R|warnings loglevel only")
    parser.add_argument("-n", action='store_true', required=False, help="R|normal loglevel only")
    return parser


class PrettyLogger(object):
    """
        H| at the start of the message signifies that this message
        needs to be run through the color conversion process.
        Without H| all color codes will be ignored.
        use PrettyLogger(log_level="warn", msg="H|sup yo (colorcode|highlight) (colorcode|me MULTIPLE TIMES!)")

    """

    _log_level_map = {
        "Normal"  : ["green", "\x1b[32m"],
        "Warning" : ["red", "\x1b[31m"],
        "error"   : ["red", "\x1b[31m"],
        "warn"    : ["yellow", "\x1b[33m"],
        "info"    : ["green", "\x1b[32m"],
        "verbose" : ["blue", "\x1b[34;1m"],
        "other"   : ["cyan", "\x1b[36m"],
        "invalid" : ["red", "\x1b[36m"],
        "creset"  : ["creset", "\x1b[0m"],
        "debug"   : ["magenta", "\x1b[35m"],
    }

    _color_map = {
        "red": "\x1b[31m",
        "yellow": "\x1b[33m",
        "green": "\x1b[32m",
        "blue": "\x1b[34m",
        "cyan": "\x1b[36m",
        "magenta": "\x1b[35m",
        "hred": "\x1b[31;1m",
        "hyellow": "\x1b[33;1m",
        "hblue": "\x1b[34;1m",
        "hgreen": "\x1b[32;1m",
        "hcyan": "\x1b[36;1m",
        "hmagenta": "\x1b[35;1m",
        "creset": "\x1b[0m",
    }

    def highlight(self, msg):
        if msg.startswith("H|"):
            reset_color = self._color_map["creset"]
            msg = msg.partition("|")[2]
            matches = re.findall(r'\((.*?)\)', msg)
            for each in matches:
                original_msg = f"({each})"
                msg_split = each.split('|')
                color_code = msg_split[0]
                words = msg_split[1]
                if color_code not in self._color_map:
                    highlight_color = self._color_map["yellow"]
                else:
                    highlight_color = self._color_map[color_code]
                words = f'{highlight_color}{words}{reset_color}'
                msg = msg.replace(original_msg, words)
        return msg

    def fix_header(self):
        return "[\033[92m{} - {}\x1b[0m]".format(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), self.header)

    def __init__(self, **kwargs):
        log_level = kwargs["log_level"]
        if log_level not in self._log_level_map:
            log_level = "invalid"
        msg = kwargs["msg"]
        self.log_level_color = self._log_level_map[log_level][1]
        self.log_level_color_reset = self._log_level_map["creset"][1]
        self.log_level = ":{}{:>7s}{}:".format(self.log_level_color, log_level, self.log_level_color_reset)
        called = str(list(sys._current_frames().items())[0][0])
        self.header = [v[1] for k, v in enumerate(inspect.stack()) if called not in str(v[0])][1].split('/')[-1]
        self.header = self.fix_header()
        msg = self.highlight(msg)
        print("{} {} {}".format(self.header, self.log_level, msg))


config.load_kube_config()
contexts = config.list_kube_config_contexts()
context = [context.get('name').split('.')[0] for context in contexts[0]]
clean_context = []
for each in context:
    if each not in clean_context:
        clean_context.append(each)

# ghetto


if __name__ == "__main__":
    parser = config_parser()
    args = parser.parse_args()
    my_filter = args.f if args.f is not None else None
    if args.n:
        message_type = "Normal"
    if args.w:
        message_type = "Warning"
    else:
        message_type = None
    wrapper = TextWrapper(initial_indent="* ")
    chosen_context, _ = pick(clean_context, title="Pick the context to load")
    core_client = client.CoreV1Api(api_client=config.new_client_from_config(context=chosen_context))
    w = watch.Watch()
    try:
        for event in w.stream(core_client.list_event_for_all_namespaces, _request_timeout=300):
            action = list(event.values())[0]
            metadata = event['object'].metadata
            namespace = metadata.namespace
            event_type = event['object'].type
            name = metadata.name
            message = event['object'].message.replace('(', "[").replace(")", "]")
            context_len = len(chosen_context)
            wrapped = False
            print_msg = False
            if event_type:
                if len(message) > 120:
                    wrapped = True
                    message = "\n".join(wrap(f"\n{message.lstrip()}", break_on_hyphens=False, width=100)).lstrip()
                if my_filter:
                    #print(f"filtering for {my_filter}")
                    #print(name, namespace, event)
                    r = re.compile(f'.*{my_filter}.*')
                    my_list = [name, namespace, message, event_type]
                    matches = list(filter(r.match, my_list))    
                    #print(matches)
                    if matches:
                        if wrapped:
                            PrettyLogger(log_level=event_type, msg=f"H|(hmagenta|{chosen_context:{context_len}.{context_len}}):(magenta|{namespace:>15.15}):(hblue|{name:<20.20}) - [MULTI] {message}")
                            #print(type(message))
                            #print(message)
                        else:
                            PrettyLogger(log_level=event_type, msg=f"H|(hmagenta|{chosen_context:{context_len}.{context_len}}):(magenta|{namespace:>15.15}):(hblue|{name:<20.20}) - {message}")
                else:
                    if wrapped:
                        PrettyLogger(log_level=event_type, msg=f"H|(hmagenta|{chosen_context:{context_len}.{context_len}}):(magenta|{namespace:>15.15}):(hblue|{name:<20.20}) - [MULTI] {message}")
                        #print(type(message))
                        #print(message)
                    else:
                        PrettyLogger(log_level=event_type, msg=f"H|(hmagenta|{chosen_context:{context_len}.{context_len}}):(magenta|{namespace:>15.15}):(hblue|{name:<20.20}) - {message}")
    except ProtocolError as e:
        PrettyLogger(log_level="warn", msg="Web Stream connection broken! Rebuilding")
        pass