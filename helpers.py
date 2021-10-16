from lux.game_map import Cell, Resource

class PriorityCell():
    def __init__(self, cell: Cell, resource: Resource):
       self.cell = cell
       self.resource = resource

class PiorityData():
    def __init__(self, p_cell: PriorityCell, distance: int):
       self.p_cell = p_cell
       self.distance = distance