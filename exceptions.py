class DeserializationError(Exception):
    pass

class VersionMismatchError(DeserializationError):
    pass

class UnknownNodeError(DeserializationError):
    pass