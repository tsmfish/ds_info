import os
import re
from threading import Lock

print_message_format = "> {0} < : {1}"
progress_message_format = "action {action} on {host} progress {progress}"
__progress_char_set = ['\\', '+', '|', 'x', '/', '+', '-', 'x']
__progress_index = 0
__progress_visible = False
__progress_lock = Lock()


class COLORS(object):

    class STYLE:
        normal    = 0
        highlight = 1
        underline = 4
        blink     = 5
        negative  = 7

    class FOREGROUND:
        black   = 30
        red     = 31
        green   = 32
        yellow  = 33
        blue    = 34
        magenta = 35
        cyan    = 36
        white   = 37

    class BACKGROUND:
        black   = 40
        red     = 41
        green   = 42
        yellow  = 43
        blue    = 44
        magenta = 45
        cyan    = 46
        white   = 47

    end = "\x1b[0m"
    colored = '\x1b[{style};{foreground};{background}m'

    black   = colored.format(style=STYLE.normal, foreground=FOREGROUND.black  , background=BACKGROUND.white)
    red     = colored.format(style=STYLE.normal, foreground=FOREGROUND.red    , background=BACKGROUND.black)
    green   = colored.format(style=STYLE.normal, foreground=FOREGROUND.green  , background=BACKGROUND.black)
    yellow  = colored.format(style=STYLE.normal, foreground=FOREGROUND.yellow , background=BACKGROUND.black)
    blue    = colored.format(style=STYLE.normal, foreground=FOREGROUND.blue   , background=BACKGROUND.black)
    magenta = colored.format(style=STYLE.normal, foreground=FOREGROUND.magenta, background=BACKGROUND.black)
    cyan    = colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan   , background=BACKGROUND.black)
    white   = colored.format(style=STYLE.normal, foreground=FOREGROUND.white  , background=BACKGROUND.black)

    colors = [white,
              cyan,
              green,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.cyan),
              yellow,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.green),
              magenta,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan, background=BACKGROUND.blue),
              black,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.yellow),
              ]

    warning = yellow
    fatal = colored.format(style=STYLE.highlight, foreground=FOREGROUND.red, background=BACKGROUND.black)
    error = red
    ok = green
    info = cyan

    cursor_up_lines   = "\x1b[{0}A"
    cursor_up_line    = cursor_up_lines.format(1)
    cursor_down_lines =  "\x1b[{0}B"
    cursor_down_line  = cursor_down_lines.format(1)

    cursor_to_position = "\x1b[{0};{1}H"

    def move_cursor_to_position(row, column):
        return COLORS.cursor_to_position.format(row, column)

    clear_line = "\x1b[2K"
    clear_line_to_end = "\x1b[0K"
    clear_line_to_begin = "\x1b[1K"
    clear_screen = "\x1b[2J"
    clear_screen_to_begin = "\x1b[1J"
    clear_screen_to_end = "\x1b[0J"
    clear_screen_with_scrollback = "\x1b[3J"


__ds_host_name_parse = re.compile(r'\b([A-Z]+?\d+?-[A-Z]{3})(\d+?)\b', re.IGNORECASE)


def ds_print(host, message, print_lock=None, log_file_name=None, host_color=None, message_color=None, progress=None):
    """
    Print colored message with formatted header
    
    :param host:
    :type host: str
    :param message:
    :type message: str
    :param print_lock:
    :type print_lock: Lock()
    :param log_file_name: 
    :type log_file_name: str
    :param host_color: 
    :type host_color: COLORS
    :param message_color: 
    :type message_color: COLORS
    :return: None
    """

    if __ds_host_name_parse.findall(host):
        site_preamble, site_number = __ds_host_name_parse.findall(host)[0]
        host = "{0}{1:<4d}".format(site_preamble, int(site_number))

    if host_color and message_color:
        colored_host = host_color + host + COLORS.end
        colored_message = message_color + message + COLORS.end
    elif host_color:
        colored_host = host_color + host + COLORS.end
        colored_message = host_color + message + COLORS.end
    elif message_color:
        colored_host = host
        colored_message = message_color + message + COLORS.end
    else:
        colored_host = host
        colored_message = message

    if print_lock:
        try:
            print_lock.acquire()
        except:
            pass

    try:
        __progress_lock.acquire()
    except:
        pass

    if __progress_visible:
        print COLORS.cursor_up_line + COLORS.cursor_up_line + COLORS.clear_line
        __progress_visible = False

    if progress:
        print print_message_format.format(action=colored_message, host=colored_host, progress=__progress_char_set[__progress_index])

        __progress_visible = True
        __progress_index = (__progress_index + 1) % len(__progress_char_set)
    else:
        print print_message_format.format(colored_host, colored_message)

    try:
        print_lock.release()
    except:
        pass

    if log_file_name:
        try:
            with open(log_file_name, 'a+') as log_file:
                log_file.write("{0}\n".format(message))
                log_file.close()
        except IOError:
            pass


def is_contains(regexp, text):
    """
    Check that {text} contains {regexp} 

    :param regexp:
    :type regexp: str
    :param text:
    :type text: str
    :return: True if string contains regular expression
    :rtype: bool
    """
    if re.search(regexp, text):
        return True
    else:
        return False


def extract(regexp, text):
    """

    :param regexp: regular expression
    :type regexp: str
    :param text: source for extracting
    :type text: str
    :return: first occur regular expression
    :rtype: str
    """
    try:
        return re.findall(regexp, text)[0]
    except IndexError:
        return ""


def ds_compare(left, right):
    """
    
    :param left: switch name
    :type left: str 
    :param right: switch name
    :type right: str
    :return: -1 / 0 / 1 according compare 
    """
    __parser = re.compile(r'([a-z]+?)(\d+?)-([a-z]+?)(\d+)', re.IGNORECASE)
    try:
        l1, l2, l3, l4 = __parser.findall(left)[0]
        r1, r2, r3, r4 = __parser.findall(right)[0]
        if l1 != r1:
            return (1, -1)[l1 < r1]
        elif l3 != r3:
            return (1, -1)[l3 < r3]
        elif l4 != r4:
            return (1, -1)[int(l4) < int(r4)]
        elif l2 != r2:
            return (1, -1)[int(l2) < int(r2)]
        else:
            return 0

    except IndexError:
        return "" != ""
    except TypeError:
        return "" != ""


def get_terminal_dimension():
    try:
        return os.popen('stty size', 'r').read().split()
    except:
        return 0, 0
