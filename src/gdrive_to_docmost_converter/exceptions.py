class UnknownCommandError(Exception):
    def __init__(self, command: str):
        super().__init__(f"Unknown command: '{command}'")
        self.command = command


class ImportFailedError(Exception):
    def __init__(self, import_job_id: str, message: str | None):
        super().__init__(f"Import failed for import job '{import_job_id}': {message or 'unknown error'}")
        self.import_job_id = import_job_id


class ImportTimeoutError(Exception):
    def __init__(self, import_job_id: str):
        super().__init__(f"Import timed out for import job '{import_job_id}'")
        self.import_job_id = import_job_id
