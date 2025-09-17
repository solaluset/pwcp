# fmt: off
# this should NOT work as we are in the .py file
#define b B  # noqa[E265]

from .something import c  # noqa[F401]

b = 'c'
