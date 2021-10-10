import math
from typing import List
from lux.game import Game, Unit, City, Player, CityTile
from lux.game_map import Cell, RESOURCE_TYPES, Position
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from collections import deque
import random
from lux import annotate
from helpers import PiorityData
# logfile = "agent.log"
# open(logfile,"w")

# p_logfile = "priority.log"
# open(p_logfile,"w")

#hyper params
FUEL_IN_CITY_BEFORE_LEAVING = 320
RESOURCE_MIN = 50
EXPLORE_AGRO = 2
FUEL_MISSMATCH = 500
START_EXPLORE_STEP = 5

DIRECTIONS = Constants.DIRECTIONS
game_state: Game = None
width = 32
height = 32
build_location = None

unit_to_priority_tile_dict = {}
worker_positions = {}
priority_build_tiles: List[Cell] = []

def mylog(msg):
    False
    # with open(logfile,"a") as f:
    #     f.write(msg+"\n")

def plog(msg):
    False
    # with open(p_logfile,"a") as f:
    #     f.write(msg+"\n")

def have_unresearched_resources(cell: Cell, player: Player):
    if cell.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): return True
    if cell.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): return True
    return False

def surrounding_unit_count(cell: Cell, workers: List[Unit]):
    count = 0
    for c in get_surronding_cells(cell):
        if has_units(c, workers):
            count = count + 1
    return count

def surrounding_cell_has_resources(cell: Cell, player: Player):
    for c in get_surronding_cells(cell):
        if c.has_resource() == True and have_unresearched_resources(c, player) == False and c.resource.amount > RESOURCE_MIN:
            return True
    return False

def get_resource_tiles(game_state, width, height):
    resource_tiles: list[Cell] = []
    for y in range(height):
        for x in range(width):
            cell: Cell = game_state.map.get_cell(x, y)
            if cell.has_resource() and cell.resource.amount > RESOURCE_MIN:
                resource_tiles.append(cell)
    return resource_tiles

def get_surronding_cells(current_cell: Cell) -> List[Cell]:
    valid_cells: List[Cell] = []
    x = current_cell.pos.x
    y = current_cell.pos.y
    if x - 1 > 0:
        ml = game_state.map.get_cell(x - 1, y)
        valid_cells.append(ml)
    if y - 1 > 0:
        tc = game_state.map.get_cell(x, y -1)
        valid_cells.append(tc)
    if y + 1 < height:
        bc = game_state.map.get_cell(x, y + 1)
        valid_cells.append(bc)
    if x + 1 < width:
        mr = game_state.map.get_cell(x + 1, y)
        valid_cells.append(mr)
    return valid_cells

def has_units(cell: Cell, workers: List[Unit]):
    for worker in workers:
        if worker.pos == cell.pos:
            return True
    return False
    
def get_priority_tiles(resource_tiles: List[Cell], player: Player, workers: List[Unit]):
    priority_list = []
    for resource_tile in resource_tiles:
        current_cell = game_state.map.get_cell(resource_tile.pos.x, resource_tile.pos.y)
        if current_cell.has_resource() == True and have_unresearched_resources(current_cell, player) == False and current_cell.resource.amount > 100:
            for cell in get_surronding_cells(current_cell):
                if cell.has_resource() == False and ( cell.citytile == None or cell.citytile == False) and has_units(cell, workers) == False:
                    priority_list.append(cell) 
    return priority_list

def get_close_city(player, unit):
    closest_dist = math.inf
    closest_city_tile = None
    for k, city in player.cities.items():
        for city_tile in city.citytiles:
            dist = city_tile.pos.distance_to(unit.pos)
            if dist < closest_dist:
                closest_dist = dist
                closest_city_tile = city_tile
    return closest_city_tile

def find_empty_tile_near(near_what: Cell, game_state, observation):
    build_location = None
    dirs = [(1,0), (0,1), (-1,0), (0,-1)]
    # may later need to try: dirs = [(1,-1), (-1,1), (-1,-1), (1,1)] too.
    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(near_what.pos.x+d[0], near_what.pos.y+d[1])
            #logging.INFO(f"{observation['step']}: Checking:{possible_empty_tile.pos}")
            if possible_empty_tile in priority_build_tiles and possible_empty_tile.resource == None and possible_empty_tile.road == 0 and possible_empty_tile.citytile == None:
                build_location = possible_empty_tile
                mylog(f"{observation['step']}: Found build location:{build_location.pos}")

                return build_location
        except Exception as e:
            mylog(f"{observation['step']}: While searching for empty tiles:{str(e)}")


    mylog(f"{observation['step']}: Couldn't find a tile next to, checking diagonals instead..")

    dirs = [(1,-1), (-1,1), (-1,-1), (1,1)] 
    # may later need to try: dirs = [(1,-1), (-1,1), (-1,-1), (1,1)] too.
    for d in dirs:
        try:
            possible_empty_tile = game_state.map.get_cell(near_what.pos.x+d[0], near_what.pos.y+d[1])
            #logging.INFO(f"{observation['step']}: Checking:{possible_empty_tile.pos}")
            if possible_empty_tile.resource == None and possible_empty_tile.road == 0 and possible_empty_tile.citytile == None:
                build_location = possible_empty_tile
                mylog(f"{observation['step']}: Found build location:{build_location.pos}")

                return build_location
        except Exception as e:
            mylog(f"{observation['step']}: While searching for empty tiles:{str(e)}")

    mylog(f"{observation['step']}: Something likely went wrong, couldn't find any empty tile")
    return None

def find_closest_unused_priority_cell(unit: Unit, observation):
    pbt_with_dist_dict = {}
    for tile in priority_build_tiles:
        dist = unit.pos.distance_to(tile.pos)
        pbt_with_dist_dict[f"{tile.pos.x},{tile.pos.y}"] = dist

    pbt_with_dist_dict = {k: v for k, v in sorted(pbt_with_dist_dict.items(), key=lambda item: item[1])}
    for pos_str in pbt_with_dist_dict:
        if random.randint(0,EXPLORE_AGRO) == 1 or observation['step'] < START_EXPLORE_STEP:
            pos_l = pos_str.split(",")
            possible_build_location = game_state.map.get_cell(int(pos_l[0]), int(pos_l[1]))
            if possible_build_location.resource == None and possible_build_location.road == 0 and possible_build_location.citytile == None:
                return possible_build_location
        else:
            continue
    
    mylog(f"{observation['step']}: Something likely went wrong, couldn't find any empty tile")
    return None
    

def add_move_to_direction(unit: Unit, new_pos: Position, move_list: List[Position]):
    direct = unit.pos.direction_to(new_pos)
    new_pos = unit.pos.translate(direct,1)
    if new_pos in move_list:
        ran_dir = random.choice(Constants.DIRECTIONS)
        mylog(f"Move in random direction: {ran_dir}")
        ran_pos = unit.pos.translate(direct,1)
        move_list.append(ran_pos)
        return unit.move(ran_dir), move_list
    else:
        move_list.append(new_pos)
        return unit.move(direct), move_list

def agent(observation, configuration):
    global game_state
    global width
    global height
    global build_location
    global unit_to_priority_tile_dict
    global worker_positions
    global priority_build_tiles

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
    else:
        game_state._update(observation["updates"])
    
    actions = []

    ### AI Code goes down here! ### 
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]
    width, height = game_state.map.width, game_state.map.height
    resource_tiles = get_resource_tiles(game_state, width, height)
    workers = [u for u in player.units if u.is_worker()]
    carts = [u for u in player.units if u.is_cart()]
    priority_build_tiles = get_priority_tiles(resource_tiles, player, workers) 

    cities: List[City] = player.cities.values()
    city_tiles: List[CityTile] = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)
    
    # city_w_highest_fuel = max(cities, key=lambda city: city.fuel)
    # city_w_lowest_fuel = min(cities, key=lambda city: city.fuel)
    # fuel_missmatch = city_w_highest_fuel.fuel - city_w_lowest_fuel.fuel

    for w in workers:

        if w.id in worker_positions:
            worker_positions[w.id].append((w.pos.x, w.pos.y))
        else:
            worker_positions[w.id] = deque(maxlen=3)
            worker_positions[w.id].append((w.pos.x, w.pos.y))


    mylog(f"{observation['step']} Worker Positions {worker_positions}")

    if len(workers) == 1 and len(city_tiles) == 1 and observation['step'] < 3:
        worker = workers[0]
        unit_to_priority_tile_dict[worker.id] = game_state.map.get_cell_by_pos(worker.pos)
    else:
        for w in workers:
            if w.id not in unit_to_priority_tile_dict:
                mylog(f"{observation['step']} Found worker w/o resource {w.id}")
                tile_assignment = find_closest_unused_priority_cell(w, observation)
                unit_to_priority_tile_dict[w.id] = tile_assignment

    move_list: List[Position] = []

    for unit in player.units:
        if unit.is_worker() and unit.can_act():

            try:              
                if unit.get_cargo_space_left() > 0:
                    intened_tile: Cell = unit_to_priority_tile_dict[unit.id]
                    cell = game_state.map.get_cell(intened_tile.pos.x, intened_tile.pos.y)

                    unit_cell = game_state.map.get_cell_by_pos(unit.pos)  
                    unit_city: City = None
                    if unit_cell.citytile:
                        for c in cities:
                            if c.cityid == unit_cell.citytile.cityid:
                                unit_city = c
                    has_surrounding_res = surrounding_cell_has_resources(unit_cell, player)
                    min_fuel = FUEL_IN_CITY_BEFORE_LEAVING
                    if game_state.map_width < 32: min_fuel = FUEL_IN_CITY_BEFORE_LEAVING/2
                    if cell.pos == unit_cell.pos and has_surrounding_res and unit_city != None and unit_city.fuel < min_fuel:
                        plog(f"{player.team} - {observation['step']} - Stay put. x: {cell.pos.x}, y: {cell.pos.y}")
                        continue
                    elif cell.pos == unit_cell.pos and has_surrounding_res and unit_city != None and unit_city.fuel > min_fuel:
                        plog(f"{player.team} - {observation['step']} - Re-assign. x: {cell.pos.x}, y: {cell.pos.y}")
                        new_tile = find_closest_unused_priority_cell(unit, observation)
                        unit_to_priority_tile_dict[unit.id] = new_tile
                        move_command, move_list = add_move_to_direction(unit,new_tile.pos, move_list)
                        actions.append(move_command)
                        continue
                    elif cell.pos == unit_cell.pos and not has_surrounding_res:
                        plog(f"{observation['step']} - This should not happend. x: {cell.pos.x}, y: {cell.pos.y}")
                        # priority_str = f""
                        # for t in priority_build_tiles:
                        #     priority_str += f"{t.pos.x},{t.pos.y}\n"
                        # plog(f"{observation['step']} - priority list: {priority_str}")
                        new_tile = find_closest_unused_priority_cell(unit, observation)
                        unit_to_priority_tile_dict[unit.id] = new_tile
                        move_command, move_list = add_move_to_direction(unit,new_tile.pos, move_list)
                        actions.append(move_command)
                        continue

                    else:
                        plog(f"{player.team} - {observation['step']} - Move to tile x: {cell.pos.x}, y: {cell.pos.y}")
                        move_command, move_list = add_move_to_direction(unit,intened_tile.pos, move_list)
                        actions.append(move_command)
                    continue
                else:
                    if unit.can_build:
                        mylog(f'Building city now')
                        actions.append(unit.build_city())                    
                    # if unit is a worker and there is no cargo space left, and we have cities, lets return to them
                    elif len(player.cities) > 0:
                        mylog(f'Cannot build city yet')
                        continue
            except Exception as e:
                mylog(f"{observation['step']}: Unit error {str(e)}")

    can_create = len(city_tiles) - len(workers)

    if len(city_tiles) > 0:
        for city_tile in city_tiles:
            if city_tile.can_act():
                # if fuel_missmatch > FUEL_MISSMATCH:
                #     actions.append(city_tile.build_cart())
                city_tile_cell = game_state.map.get_cell_by_pos(city_tile.pos)
                if can_create > 0 and not city_tile.pos in move_list and surrounding_unit_count(city_tile_cell, workers) < 2:
                    actions.append(city_tile.build_worker())
                    can_create -= 1
                    mylog(f"{observation['step']}: Created a worker ")
                else:
                    actions.append(city_tile.research())
                    mylog(f"{observation['step']}: Doing research! ")
    
    return actions
