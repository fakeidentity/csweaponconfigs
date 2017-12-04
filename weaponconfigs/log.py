from logging import (Formatter, getLogger, StreamHandler, Filter,
                     INFO, DEBUG, WARN)
from logging.handlers import RotatingFileHandler, MemoryHandler
import os
import inspect
from textwrap import indent
from pathlib import Path
import re


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



class StripANSIFormatter(Formatter):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    def format(self, record):
        record.msg = self.ansi_escape.sub("", str(record.msg))
        return super(StripANSIFormatter, self).format(record)



class BufferDebugHandler(MemoryHandler):
    def shouldFlush(self, record):
        return (len(self.buffer) >= self.capacity)


    def flush(self):
        self.acquire()
        try:
            if self.target:
                for record in self.buffer:
                    if record.levelno >= self.flushLevel:
                        self.target.handle(record)
                self.buffer = []
        finally:
            self.release()



def handle_exception(logger, exc_type, exc_value, exc_trace):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_trace)
        return
    logger.error("Uncaught exception",
                 exc_info=(exc_type, exc_value, exc_trace))


def logger_setup(output_dir, script_fn):
    """ Set up logging. getlogger, add handlers, formatters, etc.
    script_fn should probably be __file__.
    returns logger
    """
    log = getLogger(modulename())
    log.setLevel(DEBUG)
    logfn = os.path.basename(script_fn).rsplit('.', 1)[0]
    logfp = os.path.join(output_dir, "{}.log".format(logfn))
    logfp = Path(logfp)
    logfp.parent.mkdir(parents=True, exist_ok=True)

    conhandler = StreamHandler()
    conhandler.setLevel(DEBUG)
    conformat = Formatter("[%(asctime)s] %(levelname)s - %(message)s",
                          "%H:%M:%S")
    conhandler.setFormatter(conformat)
    #log.addHandler(conhandler)

    memhandler = BufferDebugHandler(999999, flushLevel=INFO, target=conhandler)
    log.addHandler(memhandler)

    filehandler = RotatingFileHandler(logfp,
                                      maxBytes=5242880,
                                      backupCount=1,
                                      encoding="utf-8")
    filehandler.setLevel(DEBUG)
    fileformat = StripANSIFormatter("%(asctime)s -\t%(levelname)s\t-\t%(name)s:"
                                    "\t%(message)s\n")
    filehandler.setFormatter(fileformat)
    # Filehandler needs to be added last so its custom formatter will work?
    log.addHandler(filehandler)

    werkzeuglog = getLogger("werkzeug")
    werkzeuglog.addHandler(filehandler)

    log.addFilter(DuplicateFilter())
    log.addFilter(LongOutputFilter())
    return log