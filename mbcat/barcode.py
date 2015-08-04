
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

class EAN(object):
    """
    Implements the European Article Number (EAN)
    https://en.wikipedia.org/wiki/International_Article_Number_%28EAN%29

    For example, the EAN-13 barcode 5901234123457 has a check digit of 7 and is
    a valid barcode.
    """
    def __init__(self, code):
        if (type(code) != str) and (type(code) != unicode):
            raise ValueError('code must be a string')
        self.code = code

    weights = [3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3]
    weights13 = [1,3,1,3,1,3,1,3,1,3,1,3]
    weights8 = [3,1,3,1,3,1,3]

    @staticmethod
    def _checksum(code):
        l = list(code)
        pairs = zip(l[:12], EAN.weights13) if len(l) == 13 else \
                zip(l[:17], EAN.weights) if len(l) == 18 else \
                zip(l[:7], EAN.weights8)
        products = [int(d)*w for d,w in pairs]
        sum_products = sum(products)
        return (sum_products / 10 + 1)*10 - sum_products

    def checksum(self):
        return self._checksum(self.code)

    def __nonzero__(self):
        return self.checksum() == int(self.code[-1])
