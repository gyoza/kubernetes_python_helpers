#!/usr/bin/env python3.8
import os
import sys
import json
import logging
import urllib3
import traceback
from datetime import datetime
from kubernetes import client, config

script_path = os.path.dirname(os.path.realpath(__file__))
CONFIG_FILE = f"{script_path}/../deploy_config.json"
config.load_kube_config()
contexts = config.list_kube_config_contexts()
context = [context.get('name') for context in contexts[0]]


def get_date():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_environment(config_map, context):
    """
    finds what environment the requested context
    belongs in referenced from the deploy_config.json
    """
    desired_environment = None
    prod_clusters = config_map["clusters"]["prod"]
    nonprod_clusters = config_map["clusters"]["nonprod"]
    if context in nonprod_clusters:
        desired_environment = "nonprod"
    elif context in prod_clusters:
        desired_environment = "prod"
    if not desired_environment:
        return None
    else:
        return desired_environment


def get_version(context):
    try:
        logging.getLogger("urllib3").propagate = False
        client.configuration.urllib3.disable_warnings(True)
        urllib3.disable_warnings()        
        print(f"---- attempting to contact cluster {context}")
        client.configuration.urllib3.disable_warnings(True)
        version_client = client.VersionApi(api_client=config.new_client_from_config(context=each))
        for logger in version_client.api_client.configuration.logger.values():
            logger.removeHandler(version_client.api_client.configuration.logger_stream_handler)
        version = version_client.get_code().to_dict().get("git_version")
        return version
    except Exception as e:
        print(e)
        print(f'---- failed to contact {context}')
        return None


if __name__ == "__main__":
    config_map = json.loads(open(CONFIG_FILE, 'r').read())
    nonprod = []
    none = []
    prod = []
    all_context = []
    for each in context:
        # needs to be cleaned up -- lazy...
        try:
            each = each.split('.')[0]
        except Exception as e:
            pass
        if each in all_context:
            pass
        else:
            environment = get_environment(config_map, each)
            version = get_version(each)
            if each not in all_context:
                all_context.append(each)
            if version:
                if environment == "nonprod":
                    nonprod.append(f"cluster : {each:25} version : {version}")
                if environment == "prod":
                    prod.append(f"cluster : {each:25} version : {version}")
                if not environment:
                    none.append(f"cluster : {each:25} version : {version}")
    if none:
        print(f'\n--- environment: none ---\n')
        for each in none:
            print(f"  {each}")
    if nonprod:
        print(f'\n--- environment: nonprod ---\n')
        for each in nonprod:
            print(f"  {each}")
    if prod:
        print(f'\n--- environment: prod ---\n')
        for each in prod:
            print(f"  {each}")
