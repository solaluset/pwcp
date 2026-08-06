from .hooks import PreprocessorHooks, PWCPHooks

FILE_EXTENSIONS = [".ppy"]
HOOKS: list[PreprocessorHooks] = []

add_file_extension = FILE_EXTENSIONS.append
add_hook = HOOKS.append
add_hook(PWCPHooks())
