
class Sat:

    # TODO add other fields from observation API
    def __init__(self, x, y):
        self.width_x: int = x
        self.height_y: int = y
        self.power: int = 100
        self.fuel: int = 100
        

    def getPos(self):
        return self.x, self.y
    

    # TODO
    def update(self):
        # use API to read observation API
        return
