#!/usr/bin/env python2.6
# -*- coding: utf-8

import base64
import getpass
import optparse
import random
import threading
import time
import re
from Queue import Queue


from ds_helper import COLORS, ds_print, extract, is_contains, ds_compare

import sys
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/ecdsa-0.13-py2.6.egg/')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/requests-2.9.1-py2.6.egg')
sys.path.insert(1, '/home/erkki/.local/lib/python2.6/site-packages/paramiko-1.16.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/netmiko-1.1.0-py2.6.egg')
sys.path.insert(1, '/home/butko/.local/lib/python2.6/site-packages/scp-0.10.2-py2.6.egg/')

from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException


log_file_format = "%y%m%d_%H%M%S_{ds_name}.log"


COMPLETE, FATAL, TEMPORARY = 'complete', 'fatal', 'temporary'
NAME, RESULT, PAYLOAD = 'name', 'result', 'printouts', 'payload'


RETRY_CONNECTION_LIMIT = 5
FAIL_CONNECTION_WAIT_INTERVALS = [2, 3, 3, 7, 9, 13, 17, 25, 39]
RANDOM_WAIT_TIME = 5

ds_name_pattern = re.compile(r"\b\w+?\d-\w+?\d{0,4}\b", re.IGNORECASE)
comment_line_pattern = re.compile(r"^\s*?[#/][^\n]+$", re.IGNORECASE)
sw_pattern = re.compile(r'\bTiMOS-\S+', re.IGNORECASE)
primary_bof_image_pattern = re.compile(r'primary-image\s+?(\S+)\b', re.IGNORECASE)
both_file_pattern = re.compile(r'both\.tim', re.IGNORECASE)


TYPE, SW_VERSION, BOOT_VERSION, BOF_VERSION, NAME = 'type', 'sw version', 'boot.tim version', 'primary bof version', 'name'
HEADER, getter = 'header', 'getter'

COMMANDS = {
    TYPE: {
        HEADER: 'DS Type',
        getter: lambda connection: extract(re.compile(r'\bSAS-[XM]\b', re.IGNORECASE), execute_command(connection, 'show version'))
    },
    SW_VERSION: {
        HEADER: 'DS SW version',
        getter: lambda connection: extract(sw_pattern, execute_command(connection, 'show version'))
    },
    BOOT_VERSION: {
        HEADER: 'boot.tim version',
        getter: lambda connection: extract(sw_pattern, execute_command(connection, 'file version boot.tim'))
    },
    BOF_VERSION: {
        HEADER: 'Primary BOF version',
        getter: lambda connection: extract(sw_pattern, execute_command(connection, 'file version {0}'.format(get_primary_bof_file(connection))))
    },
}


def get_primary_bof_file(connection):
    primary_bof_conf = extract(primary_bof_image_pattern, connection.send_command('show bof'))
    if is_contains(both_file_pattern, primary_bof_conf):
        return primary_bof_conf
    else:
        return primary_bof_conf + "\\both.tim"


def execute_command(connection, command):
    try:
        return connection.send_command(command)
    except:
        return ""


def post_result(result_queue, node, result, payload):
    result_dict = {NAME: node, RESULT: result, PAYLOAD: payload}
    result_queue.put(result_dict)
    return result_dict


def get_node_info(node,
                  user,
                  password,
                  queue_result):

    time.sleep(RANDOM_WAIT_TIME * random.random())

    # Create object
    parameters = {
        'device_type': 'alcatel_sros',
        'host': node,
        'port': 22,
        'username': user,
        'password': password,
        'global_delay_factor': 1,
        'ssh_strict': False,
        'timeout': 8.0,
    }

    # Connect and get basic inform

    for tray in range(RETRY_CONNECTION_LIMIT):
        try:
            connection = ConnectHandler(**parameters)
            break
        except NetMikoTimeoutException as e:
            pass
        except NetMikoAuthenticationException as e:
            return post_result(queue_result, node, TEMPORARY, None)
        except:
            if tray == RETRY_CONNECTION_LIMIT - 1:
                return post_result(queue_result, node, TEMPORARY, None)
        time.sleep(FAIL_CONNECTION_WAIT_INTERVALS[tray])

    info = {}
    for info_iter in COMMANDS:
        try:
            info[info_iter[TYPE]] = info_iter[getter](connection)
        except IOError:
            info[info_iter[TYPE]] = ""

    return post_result(queue_result, node, COMPLETE, info)

if __name__ == "__main__":
    parser = optparse.OptionParser(description='Command execute.',
                                   usage="usage: %prog [options] -f <DS list file> | ds ds ds ... -c command",
                                   version="v 1.0.39")
    parser.add_option("-f", "--file", dest="ds_list_file_name",
                      help="file with DS list, line started with # or / will be dropped", metavar="FILE")
    parser.add_option("-n", "--no-thread", dest="no_threads",
                      help="execute nodes one by one sequentially",
                      action="store_true", default=False)
    parser.add_option("--pw", "--password", dest="secret",
                      help="encoded password",
                      type="string", default="")

    (options, args) = parser.parse_args()
    ds_list_raw = list(extract(ds_name_pattern, ds) for ds in args if extract(ds_name_pattern, ds))

    if options.ds_list_file_name:
        try:
            with open(options.ds_list_file_name) as ds_list_file:
                for line in ds_list_file.readlines(): ds_list_raw.append(line)
        except IOError as e:
            print COLORS.error+"Error while open file: {file}".format(file=options.ds_list_file_name)+COLORS.end
            print COLORS.error+str(e)+COLORS.end

    ds_list = list()
    for ds_str in ds_list_raw:
        ds = extract(ds_name_pattern, ds_str)
        if not is_contains(comment_line_pattern, ds_str) and ds and ds not in ds_list:
            ds_list.append(ds)

    if not ds_list or len(ds_list) < 1:
        print(COLORS.error+"No ds found in arguments."+COLORS.end)
        parser.print_help()
        exit()

    user = getpass.getuser()
    if options.secret:
        secret = base64.b64decode(options.secret).encode("ascii")
    else:
        secret = getpass.getpass('Password for DS:')

    print COLORS.info+"Start running: {0}".format(time.strftime("%H:%M:%S"))+COLORS.end
    start_time = time.time()

    result = {COMPLETE: list(), FATAL: list(), TEMPORARY: ds_list}

    while result[TEMPORARY]:
        result_queue, threads = Queue(), list()

        if options.no_threads or len(ds_list) == 1:
            for ds_name in result[TEMPORARY]:
                try:
                    get_node_info(ds_name,
                                  user,
                                  secret,
                                  )
                except Exception as e:
                    post_result(result_queue, ds_name, FATAL, None)
        else:
            for ds_name in result[TEMPORARY]:
                thread = threading.Thread(target=get_node_info, name=ds_name, args=(ds_name,
                                                                                    user,
                                                                                    secret,
                                                                                    result_queue))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

        result[TEMPORARY] = list()

        while not result_queue.empty():
            thread_result = result_queue.get()
            result[thread_result[RESULT]].append(thread_result[NAME])
            if thread_result[RESULT] == COMPLETE:
                result[PAYLOAD][thread_result[NAME]] = thread_result[PAYLOAD]

        # determinate ds with unhandled error and mark it as FATAL
        unhandled_ds = list()
        for ds_name in ds_list:
            if ds_name not in result[COMPLETE] and \
                            ds_name not in result[TEMPORARY] and \
                            ds_name not in result[FATAL]:
                unhandled_ds.append(ds_name)

        for ds_name in unhandled_ds:
            result[FATAL].append(ds_name)

        line_complete, line_temporary, line_fatal = '', '', ''

        for ds in sorted(result[COMPLETE], ds_compare):
            line_complete += ds + " "
        for ds in sorted(result[TEMPORARY], ds_compare):
            line_temporary += ds + " "
        for ds in sorted(result[FATAL], ds_compare):
            line_fatal += ds + " "

        if result[COMPLETE]:  print    COLORS.ok + "\nComplete on       : " + line_complete + COLORS.end
        if result[TEMPORARY]: print COLORS.warning + "Temporary fault on: " + line_temporary + COLORS.end
        if result[FATAL]:     print   COLORS.fatal + "Fatal error on    : " + line_fatal + COLORS.end

        if not result[TEMPORARY]: break  # finish try loading
        answer = ''
        while answer not in ["Y", "N"]:
            answer = raw_input("\nRepeat load on temporary faulty nodes (Y-yes): ").strip().upper()
        if answer != "Y": break
        print

    print COLORS.info + "\nFinish running: {0}".format(time.strftime("%H:%M:%S"))
    print 'Time elapsed: {0}'.format(time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))) + COLORS.end