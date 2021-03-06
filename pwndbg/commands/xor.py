#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pwndbg.commands
import pwndbg.memory


@pwndbg.commands.Command
@pwndbg.commands.OnlyWhenRunning
def xor(self, address, key, count):
    '''xor(address, key, count)

    XOR ``count`` bytes at ``address`` with the key ``key``.
    '''
    print(address,key,count)
