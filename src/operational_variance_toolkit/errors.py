"""Expected application errors and CLI exit codes."""


class ToolkitError(Exception):
    """Base class for expected toolkit failures."""

    exit_code = 1


class ConfigurationError(ToolkitError):
    """Raised when configuration input is missing, invalid, or unsupported."""

    exit_code = 3


class OutputExistsError(ToolkitError):
    """Raised when a workflow would overwrite an existing generated artifact."""

    exit_code = 4


class DatabaseError(ToolkitError):
    """Raised when a database operation fails in an expected way."""

    exit_code = 5


class DataValidationError(ToolkitError):
    """Raised when generated or loaded data fail hard validation."""

    exit_code = 6


class AnalyticalFormatError(DataValidationError):
    """Raised when an analytical manifest or encoded text is unsupported."""


class ReadSnapshotError(DatabaseError):
    """Raised when acceptance or bounded reading of a snapshot fails."""


class PublicationError(ToolkitError):
    """Raised when publish-new cannot provide its required guarantees."""

    exit_code = 5


class PublicationOwnershipError(PublicationError):
    """Raised when private staging cannot safely be cleaned or published."""


class RecordNotFoundError(DataValidationError):
    """Raised when a factual schema-3 inquiry has no matching record."""


class DuplicateCommandError(DataValidationError):
    """Raised when a WMS command ID has already been accepted."""


class IdentityError(ToolkitError):
    """Raised when an identifier or deterministic identity input is invalid."""

    exit_code = 6
