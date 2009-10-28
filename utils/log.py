
#
# general purpose logging
#

import sys
import datetime
import traceback

class Log(object):
    logging_debug = False
    
    def __init__(self, logging_debug=None):
        if logging_debug == None:
            # TODO this is crap!
            from permalink import settings
            logging_debug = settings.LOGGING_DEBUG
        self.logging_debug = logging_debug
    def set_logging_debug(self, logging_debug):
        self.logging_debug = logging_debug
    def get_logging_debug(self):
        return self.logging_debug
    
    def __format_msg__(self, prefix, msg, noalteration, indent_chars):
        if noalteration and indent_chars>0:
            raise TypeError, "Incompatible arguments: noalteration must also have 0 indent_chars"
        
        if msg == None:
            msg = ''
        if prefix == None or prefix == '':
            prefix = ''
        else:
            prefix = "(%s) " % (prefix)
        
        indent_whitespace = ''
        for i in range(0, indent_chars):
            indent_whitespace += ' '
        
        if noalteration:
            to_log = msg
        else:
            d = datetime.datetime.now()
            to_log = "[%02d/%02d/%s %02d:%02d:%02d.%06d] %s%s%s" \
                % (d.month, d.day, d.year, d.hour, d.minute, d.second, d.microsecond, prefix, indent_whitespace, msg)
        return to_log
    def __log__(self, prefix, msg, output_stream, newline, noalteration, indent_chars):
        if not newline:
            noalteration = True
        to_log = self.__format_msg__(prefix, msg, noalteration, indent_chars)
        if newline:
            print >>output_stream, to_log
        else:
            print >>output_stream, to_log,
        return True
    
    def __get_stream_out__(self):
        return sys.stdout
    def __get_stream_err__(self):
        return sys.stderr
    
    def debug(self, msg, newline=True, noalteration=False, indent_chars=0):
        if self.logging_debug:
            return self.__log__(None, "DEBUG: %s" % (msg), self.__get_stream_out__() \
                , newline, noalteration, indent_chars)
    def info(self, msg, newline=True, noalteration=False, indent_chars=0):
        return self.__log__("info", msg, self.__get_stream_out__(), newline \
            , noalteration, indent_chars)
    def error(self, msg, e=None, newline=True, noalteration=False, indent_chars=0 \
        , print_stacktrace=True):
        result = self.__log__("ERROR", msg, self.__get_stream_err__(), newline \
            , noalteration, indent_chars)
        if e and print_stacktrace:
            #(e_type, value, e_trace) = sys.exc_info()
            print traceback.format_exc()
        return result

class FileLogger(Log):
    
    output_fh = None
    
    def __init__(self, *args, **kwargs):
        Log.__init__(self, *args, **kwargs)
        if kwargs.has_key('output_file'):
            output_file = kwargs['output_file']
        else:
            from permalink import settings# this is total crap!
            output_file = settings.FILE_LOGGER_PATH
        self.output_fh = open(output_file, 'a')
    def __get_stream_out__(self):
        return self.output_fh
    def __get_stream_err__(self):
        return self.output_fh
    

#
