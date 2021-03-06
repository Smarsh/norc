
import zlib

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from norc.settings import (NORC_LOG_DIR, BACKUP_SYSTEM,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME)

def get_s3_connection():
    return S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

def get_s3_bucket(name=AWS_BUCKET_NAME):
    c = get_s3_connection()
    b = c.get_bucket(name)
    if not b:
        b = c.create_bucket(AWS_BUCKET_NAME)
    return b

def set_s3_key(key, contents):
    k = Key(get_s3_bucket())
    k.key = key
    if not isinstance(contents, basestring):
        contents = contents.read()
    k.set_contents_from_string(zlib.compress(contents, 9))

def get_s3_key(key, target=None):
    k = Key(get_s3_bucket())
    k.key = key
    contents = k.get_contents_as_string()
    try:
        contents = zlib.decompress(contents)
    except zlib.error:
        pass
    if target:
        target.write(contents)
    else:
        return contents

