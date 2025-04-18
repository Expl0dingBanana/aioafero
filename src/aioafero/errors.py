class AferoError(Exception):
    pass


class DeviceNotFound(AferoError):
    pass


class DeviceUpdateError(AferoError):
    pass


class ExceededMaximumRetries(AferoError):
    pass


class InvalidAuth(AferoError):
    pass


class InvalidResponse(AferoError):
    pass
