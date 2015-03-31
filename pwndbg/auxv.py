import gdb
import sys

import pwndbg.memory
import pwndbg.events
import pwndbg.info
import pwndbg.regs
import pwndbg.types
import pwndbg.arch

example_info_auxv_linux = """
33   AT_SYSINFO_EHDR      System-supplied DSO's ELF header 0x7ffff7ffa000
16   AT_HWCAP             Machine-dependent CPU capability hints 0xfabfbff
6    AT_PAGESZ            System page size               4096
17   AT_CLKTCK            Frequency of times()           100
3    AT_PHDR              Program headers for program    0x400040
4    AT_PHENT             Size of program header entry   56
5    AT_PHNUM             Number of program headers      9
7    AT_BASE              Base address of interpreter    0x7ffff7dda000
8    AT_FLAGS             Flags                          0x0
9    AT_ENTRY             Entry point of program         0x42020b
11   AT_UID               Real user ID                   1000
12   AT_EUID              Effective user ID              1000
13   AT_GID               Real group ID                  1000
14   AT_EGID              Effective group ID             1000
23   AT_SECURE            Boolean, was exec setuid-like? 0
25   AT_RANDOM            Address of 16 random bytes     0x7fffffffdb39
31   AT_EXECFN            File name of executable        0x7fffffffefee "/bin/bash"
15   AT_PLATFORM          String identifying platform    0x7fffffffdb49 "x86_64"
0    AT_NULL              End of vector                  0x0
"""


AT_CONSTANTS = {
    0 : 'AT_NULL',      # /* End of vector */
    1 : 'AT_IGNORE',    # /* Entry should be ignored */
    2 : 'AT_EXECFD',    # /* File descriptor of program */
    3 : 'AT_PHDR',      # /* Program headers for program */
    4 : 'AT_PHENT',     # /* Size of program header entry */
    5 : 'AT_PHNUM',     # /* Number of program headers */
    6 : 'AT_PAGESZ',    # /* System page size */
    7 : 'AT_BASE',      # /* Base address of interpreter */
    8 : 'AT_FLAGS',     # /* Flags */
    9 : 'AT_ENTRY',     # /* Entry point of program */
    10: 'AT_NOTELF',    # /* Program is not ELF */
    11: 'AT_UID',       # /* Real uid */
    12: 'AT_EUID',      # /* Effective uid */
    13: 'AT_GID',       # /* Real gid */
    14: 'AT_EGID',      # /* Effective gid */
    15: 'AT_PLATFORM',  # /* String identifying platform */
    16: 'AT_HWCAP',     # /* Machine dependent hints about processor capabilities */
    17: 'AT_CLKTCK',    # /* Frequency of times() */
    18: 'AT_FPUCW',
    19: 'AT_DCACHEBSIZE',
    20: 'AT_ICACHEBSIZE',
    21: 'AT_UCACHEBSIZE',
    22: 'AT_IGNOREPPC',
    23: 'AT_SECURE',
    24: 'AT_BASE_PLATFORM', # String identifying real platforms
    25: 'AT_RANDOM',    # Address of 16 random bytes
    31: 'AT_EXECFN',    # Filename of executable
    32: 'AT_SYSINFO',
    33: 'AT_SYSINFO_EHDR',
    34: 'AT_L1I_CACHESHAPE',
    35: 'AT_L1D_CACHESHAPE',
    36: 'AT_L2_CACHESHAPE',
    37: 'AT_L3_CACHESHAPE',
}

sys.modules[__name__].__dict__.update({v:k for k,v in AT_CONSTANTS.items()})



class AUXV(dict):
    def __init__(self):
        for field in AT_CONSTANTS.values():
            self[field] = None
    def set(self, const, value):
        name         = AT_CONSTANTS.get(const, "AT_UNKNOWN%i" % const)

        if name in ['AT_EXECFN', 'AT_PLATFORM']:
            value = gdb.Value(value).cast(pwndbg.types.pchar).string()

        self[name] = value
    def __getattr__(self, attr):
        return self[attr]
    def __str__(self):
        return str({k:v for k,v in self.items() if v is not None})

@pwndbg.memoize.reset_on_objfile
def get():
    return use_info_auxv() or walk_stack() or AUXV()

def use_info_auxv():
    example_info_auxv_linux = """
    33   AT_SYSINFO_EHDR      System-supplied DSO's ELF header 0x7ffff7ffa000
    16   AT_HWCAP             Machine-dependent CPU capability hints 0xfabfbff
    6    AT_PAGESZ            System page size               4096
    17   AT_CLKTCK            Frequency of times()           100
    3    AT_PHDR              Program headers for program    0x400040
    4    AT_PHENT             Size of program header entry   56
    5    AT_PHNUM             Number of program headers      9
    7    AT_BASE              Base address of interpreter    0x7ffff7dda000
    8    AT_FLAGS             Flags                          0x0
    9    AT_ENTRY             Entry point of program         0x42020b
    11   AT_UID               Real user ID                   1000
    12   AT_EUID              Effective user ID              1000
    13   AT_GID               Real group ID                  1000
    14   AT_EGID              Effective group ID             1000
    23   AT_SECURE            Boolean, was exec setuid-like? 0
    25   AT_RANDOM            Address of 16 random bytes     0x7fffffffdb39
    31   AT_EXECFN            File name of executable        0x7fffffffefee "/bin/bash"
    15   AT_PLATFORM          String identifying platform    0x7fffffffdb49 "x86_64"
    0    AT_NULL              End of vector                  0x0
    """

    lines = pwndbg.info.auxv().splitlines()

    if not lines:
        return None

    auxv = AUXV()
    for line in lines:
        tokens = line.split()
        const  = int(tokens[0])

        # GDB will attempt to read strings for us, we dont want this
        if '"' in tokens[-1]: tokens.pop(-1)

        value = eval(tokens[-1])
        auxv.set(const, value)
    return auxv


def find_stack_boundary(addr):
    # For real binaries, we can just use pwndbg.memory.find_upper_boundary
    # to search forward until we walk off the end of the stack.
    #
    # Unfortunately, qemu-user emulation likes to paste the stack right
    # before binaries in memory.  This means that we walk right past the
    # stack and to the end of some random ELF.
    #
    # In order to mitigate this, we search page-by-page until either:
    #
    # 1) We get a page fault, and stop
    # 2) We find an ELF header, and stop
    addr = pwndbg.memory.page_align(int(addr))
    try:
        while True:
            if b'\x7fELF' == pwndbg.memory.read(addr, 4):
                break
            addr += pwndbg.memory.PAGE_SIZE
    except gdb.MemoryError:
        pass
    return addr


def walk_stack():
    sp  = pwndbg.regs.sp

    if not sp:
        return None

    #
    # Strategy looks like this:
    #
    # 1) Find the end of the stack.
    # 2) Scan backward from the end of the stack until we find what
    #    could be an AT_NULL entry (two consecutive ULONGs)
    # 3) Scan back a little further until we find what could be an
    #   AT_ENTRY entry.
    # 4) Keep scanning back until we find something that isn't in the
    #    set of known AT_ enums.
    # 5) Vacuum up between the two.
    #
    end  = find_stack_boundary(sp)
    p = gdb.Value(end).cast(pwndbg.types.ulong.pointer())

    # Because reasons?
    if pwndbg.arch.current == 'arm':
        p -= 1

    # So we don't walk off the end of the stack
    p -= 2

    # Find a ~guess at where AT_NULL is.
    #
    # Coming up from the end of the stack, there will be a
    # marker at the end which is a single ULONG of zeroes, and then
    # the ARGV and ENVP data.
    #
    # Assuming that the ARGV and ENVP data is formed normally,
    # (i.e. doesn't include 8-16 consecutive zero-length args)
    # this should land us at the *END* of AUXV, which is the
    # AT_NULL vector.
    while p.dereference() != 0 or (p+1).dereference() != 0:
        p -= 2

    # Now we want to continue until we fine, at a minumum, AT_BASE.
    # While there's no guarantee that this exists, I've not ever found
    # an instance when it doesn't.
    #
    # This check is needed because the above loop isn't
    # guaranteed to actually get us to AT_NULL, just to some
    # consecutive NULLs.  QEMU is pretty generous with NULLs.
    for i in range(1024):
        if p.dereference() == AT_BASE:
            break
        p -= 2
    else:
        return

    # If we continue to p back, we should bump into the
    # very end of ENVP (and perhaps ARGV if ENVP is empty).
    #
    # The highest value for the vector is AT_SYSINFO_EHDR, 33.
    while int((p-2).dereference()) < 37:
        p -= 2

    # Scan them into our structure
    auxv = AUXV()
    while True:
        const = int((p+0).dereference())
        value = int((p+1).dereference())

        if const == AT_NULL:
            break

        auxv.set(const, value)
        p += 2

    return auxv
