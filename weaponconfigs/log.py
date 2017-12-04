from logging import (Formatter, getLogger, StreamHandler, Filter,
                     INFO, DEBUG, WARN)
from logging.handlers import RotatingFileHandler
import os
import inspect
from textwrap import indent
from pathlib import Path


def modulename():
    """
    'module.child.grandchild'
    """
    modlist = [x for x in inspect.stack() if x[3] == "<module>"][::-1]
    modnames = []
    for i, frame in enumerate(modlist):
        modname = inspect.getmodulename(modlist[i][1])
        if modname:
            modnames.append(modname)
    return ".".join(modnames)


log = getLogger(modulename())

class DuplicateFilter(Filter):
# https://stackoverflow.com/a/44692178
    def filter(self, record):
        current_log = (record.module, record.levelno, record.msg)
        if current_log != getattr(self, "last_log", None):
            self.last_log = current_log
            return True
        return False


class LongOutputFilter(Filter):
    msgprefix = " " * 8
    def filter(self, record):
        # If MSG contains newlines it's probably already formatted a bit.
        # I want to see it how it's meant to be seen.
        if "\n" in record.msg:
            line1, rest_of_msg = record.msg.split("\n", 1)
            # But I still want to be able to visually scan the log quickly so...
            # Indicate where the message really starts
            line1 = ">" * len(self.msgprefix) + line1 + "\n"
            record.msg = "\n" + line1 + indent(rest_of_msg, self.msgprefix)
        return True


def handle_exception(logger, exc_type, exc_value, exc_trace):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_trace)
        return
    logger.error("Uncaught exception",
                 exc_info=(exc_type, exc_value, exc_trace))


def logger_setup(output_dir, script_fn, debug=False):
    """ Set up logging. getlogger, add handlers, formatters, etc
    script_fn should probably be __file__
    """
    log = getLogger(modulename())
    log.setLevel(DEBUG)
    #logfn = os.path.basename(__file__).rsplit('.', 1)[0]
    logfn = os.path.basename(script_fn).rsplit('.', 1)[0]
    logfp = os.path.join(output_dir, "{}.log".format(logfn))
    logfp = Path(logfp)
    logfp.parent.mkdir(parents=True, exist_ok=True)
    filehandler = RotatingFileHandler(logfp,
                                      maxBytes=5242880,
                                      backupCount=1,
                                      encoding="utf-8")
    filehandler.setLevel(DEBUG)
    conhandler = StreamHandler()
    if debug:
        conhandler.setLevel(DEBUG)
    else:
        conhandler.setLevel(INFO)
    conformat = Formatter("[%(asctime)s] %(levelname)s - %(message)s",
                          "%H:%M:%S")
    fileformat = Formatter("%(asctime)s -\t%(levelname)s\t-\t%(name)s:"
                           "\t%(message)s\n")
    filehandler.setFormatter(fileformat)
    conhandler.setFormatter(conformat)
    log.addHandler(filehandler)
    log.addHandler(conhandler)

    werkzeuglog = getLogger("werkzeug")
    werkzeuglog.addHandler(filehandler)

    log.addFilter(DuplicateFilter())

    log.addFilter(LongOutputFilter())
    return log