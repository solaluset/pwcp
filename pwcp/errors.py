class PreprocessorError(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        self.msg = args[0] if args else None
