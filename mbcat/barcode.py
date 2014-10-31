
class UPC(object):
    def __init__(self, code):
        self.code = code

    @staticmethod
    def checksum_isbn(code):
        s = 0
        for c in code:
            s += int(c)
        return s % 10

    @staticmethod
    def check_upc_a(code):
        """Check the format of a potential UPC code"""
        return (len(code) == 12) and \
            code.isdigit() and \
            (UPC.checksum_upc_a(code) == int(code[11]))

    @staticmethod
    def checksum_upc_a(code):
        """Implementation of the algorithm described in:
http://en.wikipedia.org/wiki/Universal_Product_Code#Check_digits
"""
        digits = [int(c) for c in code]
        step_1 = 3 * sum(digits[0:11:2])
        step_2 = step_1 + sum(digits[1:10:2])
        step_3 = step_2 % 10
        step_4 = step_3 if step_3 == 0 else 10 - step_3
        return step_4

    def variations(self):
        """
        Returns a list of possible variations
        """
        barCodes = [self.code]
        if self.code.startswith('0'):
            barCodes.append(self.code[1:])
            barCodes.append(self.code[1:]+str(UPC.checksum_isbn(self.code)))
            barCodes.append(self.code[1:]+str(UPC.checksum_upc_a(self.code)))
        else:
            barCodes.append('0'+self.code)
        barCodes.append(self.code+str(UPC.checksum_isbn(self.code)))
        barCodes.append(self.code+str(UPC.checksum_upc_a(self.code)))

        return barCodes


