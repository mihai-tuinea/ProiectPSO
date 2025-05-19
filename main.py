import math

### CONSTANTS AND INITIALIZATION ###

UA = 16  # each unit is 16 bytes
TOTAL_UAs = 4096  # total number of UAs available on the disk
HDD_SIZE = TOTAL_UAs * UA  # size in bytes
UAs_for_FAT = 512  # FAT occupies 512 UAs
FAT_SIZE = UAs_for_FAT * UA  # size in bytes
UAs_for_ROOT = 64  # ROOT occupies 64 UAs
ROOT_SIZE = UAs_for_ROOT * UA  # size in bytes

# regulile de completare a structurii FAT
FREE = 0
FAT_RESERVED = 1
ROOT_RESERVED = 2
EOF = 3  # end of file
BAD = 4

FAT = [FREE] * TOTAL_UAs  # each UA will be marked as FREE
ROOT = []  # each entry here is an instance of File class
HDD = bytearray(HDD_SIZE)

for ind in range(UAs_for_FAT):
    FAT[ind] = FAT_RESERVED  # first NR_FAT UAs are reserved for FAT
for ind in range(UAs_for_FAT, UAs_for_FAT + UAs_for_ROOT):
    FAT[ind] = ROOT_RESERVED  # then reserves NR_ROOT UAs for ROOT


class File:
    """
    UA's 16 bytes limit is hardcoded in this class
    """
    def __init__(self, name, extension, size, startUA, attr):
        self.name = name[:8]
        self.extension = extension[:3]
        self.size = size & 0xFFFF # fit into 2 bytes
        self.startUA = startUA & 0xFFFF
        self.attr = attr & 0xFF


### HELPER FUNCTIONS ###

def generateContent(length, mode):
    if mode == "-ALFA":
        source = b"abcdefghijklmnopqrstuvwxyz"
    elif mode == "-NUM":
        source = b"0123456789"
    elif mode == "-HEX":
        source = b"0123456789ABCDEF"
    else:
        return b""

    # this repeats the source until it reaches 'length' bytes
    repeated = source * (length // len(source) + 1)
    # then returns the first 'length' bytes
    return repeated[:length]


def splitCommand(command, expectedArgs):
    parts = command.split()
    if len(parts) != expectedArgs:
        return None
    return parts


def splitFileName(fileName):
    if '.' not in fileName:
        return None, None
    return fileName.split('.')


def findFileIndex(name, extension):
    for i, f in enumerate(ROOT):
        if f.name == name and f.extension == extension:
            return i
    return None


def allocateUAsAndWrite(content, nr_UAs):
    # finds all free UAs in the HDD
    free_UAs = [i for i in range(UAs_for_FAT + UAs_for_ROOT, TOTAL_UAs) if FAT[i] == FREE]
    if len(free_UAs) < nr_UAs:
        return None, False  # not enough space

    # takes the first nr_UAs blocks then writes them
    allocated = free_UAs[:nr_UAs]
    for i in range(nr_UAs):
        # converts the UA index to a byte range ('start' to 'end')
        start = allocated[i] * UA
        end = start + UA
        HDD[start:end] = content[i * UA:(i + 1) * UA]

        if i < nr_UAs - 1:
            # updates the FAT so each UA points to the next allocated UA
            FAT[allocated[i]] = allocated[i + 1]
        else:
            FAT[allocated[i]] = EOF

    return allocated[0], True  # return starting UA and success


### COMMANDS HANDLING ###

def handleDIR(command):
    if len(ROOT) == 0:
        print("no files found")
        return

    if "-a" in command:
        for file in ROOT:
            print(f"{file.name}.{file.extension}\t{file.size} bytes")
    else:
        for file in ROOT:
            print(f"{file.name}.{file.extension}")


def handleCREATE(command):
    parts = splitCommand(command, 4)
    if parts is None:
        print("invalid CREATE command")
        print("usage: CREATE name.extension size -MODE")
        return

    fileName = parts[1]
    size = int(parts[2])
    mode = parts[3]

    name, extension = splitFileName(fileName)
    if None in (name, extension):
        print("the file name must include its extension")
        print("usage: name.extension")
        return

    if findFileIndex(name, extension) is not None:
        print(f"{name}.{extension} already exists")
        return

    nr_UAs = math.ceil(size / UA)

    content = generateContent(size, mode)
    if not content:
        print("invalid mode")
        print("use -ALFA, -NUM or -HEX")
        return

    startUA, success = allocateUAsAndWrite(content, nr_UAs)
    if not success:
        print("not enough free UAs for this file")
        return

    # adds the file to ROOT
    entry = File(name, extension, size, startUA, 0)
    ROOT.append(entry)
    print(f"{name}.{extension} created successfully")


def handleDELETE(command):
    parts = splitCommand(command, 2)
    if parts is None:
        print("invalid DELETE command")
        print("usage: DELETE name.extension")
        return

    fileName = parts[1]

    name, extension = splitFileName(fileName)
    if None in (name, extension):
        print("the file name must include its extension")
        print("usage: name.extension")
        return

    index = findFileIndex(name, extension)
    if index is None:
        print("WARNING: file not found")
        return

    startUA = ROOT[index].startUA  # index of the first used UA
    # marks the occupied UAs in FAT as FREE
    while startUA != EOF:
        nextUA = FAT[startUA]
        FAT[startUA] = FREE
        startUA = nextUA if nextUA != EOF else EOF

    del ROOT[index]
    print(f"{fileName} deleted successfully.")


def handleRENAME(command):
    parts = splitCommand(command, 3)
    if parts is None:
        print("invalid RENAME command")
        print("usage: RENAME oldName.extension newName.extension")
        return

    oldFileName, newFileName = parts[1], parts[2]

    oldName, oldExt = splitFileName(oldFileName)
    newName, newExt = splitFileName(newFileName)

    if None in (oldName, oldExt, newName, newExt):
        print("file names must include their extensions")
        print("usage: name.extension")
        return

    index = findFileIndex(oldName, oldExt)
    if index is None:
        print("WARNING: file not found")
        return

    ROOT[index].name = newName
    ROOT[index].extension = newExt
    print(f"{oldFileName} renamed to {newFileName}")


def handleCOPY(command):
    parts = splitCommand(command, 3)
    if parts is None:
        print("invalid COPY command")
        print("usage: COPY source.extension destination.extension")
        return

    srcFileName = parts[1]
    destFileName = parts[2]

    srcName, srcExtension = splitFileName(srcFileName)
    destName, destExtension = splitFileName(destFileName)

    if None in (srcName, srcExtension, destName, destExtension):
        print("file names must include their extensions")
        print("usage: name.extension")
        return

    # check if source exists
    srcIndex = findFileIndex(srcName, srcExtension)
    if srcIndex is None:
        print("WARNING: source file not found")
        return

    # check if destination already exists
    if findFileIndex(destName, destExtension) is not None:
        print("WARNING: destination file already exists")
        return

    srcFile = ROOT[srcIndex]
    size = srcFile.size
    nr_UAs = math.ceil(size / UA)

    # allocate UAs and copy content from source
    content = bytearray()
    currentUA = srcFile.startUA  # sets currentUA to the starting UA index
    while currentUA != EOF:
        # same logic as in the allocation function
        start = currentUA * UA
        end = start + UA
        # adds the block to content
        content += HDD[start:end]
        # chains the FAT
        currentUA = FAT[currentUA]

    startUA, success = allocateUAsAndWrite(content, nr_UAs)
    if not success:
        print("not enough free space to copy the file")
        return

    # create the new file entry
    newEntry = File(destName, destExtension, size, startUA, 0)
    ROOT.append(newEntry)
    print(f"{destFileName} copied successfully.")


def handleCommand(command):
    if command.startswith("DIR"):
        handleDIR(command)
    elif command.startswith("CREATE"):
        handleCREATE(command)
    elif command.startswith("DELETE"):
        handleDELETE(command)
    elif command.startswith("RENAME"):
        handleRENAME(command)
    elif command.startswith("COPY"):
        handleCOPY(command)
    else:
        print("unknown command")
        print("list of available commands:")
        print("DIR | CREATE | DELETE | RENAME | COPY | EXIT")


if __name__ == '__main__':
    while True:
        cmd = input("my_OS> ").strip()
        if cmd.lower().startswith("exit"):
            print("exiting program..")
            break
        else:
            handleCommand(cmd)
