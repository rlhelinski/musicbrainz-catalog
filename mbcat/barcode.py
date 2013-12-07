
class UPC(object):
    def __init__(self, code):
        self.code = code

    @staticmethod
    def checksum(code):
        s = 0
        for c in code:
            s += int(c)
        return s % 10

    def variations(self):
        """
        Returns a list of possible variations
        """
        barCodes = [self.code]
        if self.code.startswith('0'):
            barCodes.append(self.code[1:])
            barCodes.append(self.code[1:]+str(UPC.checksum(self.code)))
        else:
            barCodes.append('0'+self.code)
        barCodes.append(self.code+str(UPC.checksum(self.code)))
        if self.code.endswith(str(UPC.checksum(self.code[:-1]))):
            barCodes.append(self.code[:-2])

        return barCodes


