import time, os, copy, pickle
import pandas as pd, numpy as np
import ray
from solver import ConstraintSolver, total_building_energy_costs, _update_building

@ray.remote
def solve(building, components, config):
        solutions, costs = [], []
        try:
            building._erase_equipment()
            print(f'solving building: {building.uuid}')
            start_time = time.time()
            solver = ConstraintSolver(building, components, config=config)
            solutions, costs = solver.get_solutions()   
            print(f'{building.uuid} solving time (sec): {time.time() - start_time :.1f}')
        except Exception as e:
            print(f'error calculating building {building.uuid}: {str(e)}')
        return solutions, costs  

class RaySolver():
    def __init__(self, building, possible_components, cache_storage='./', config={}, ray_rate=1.0):
        self.components = possible_components
        self.cache_storage = cache_storage
        self.building = building
        self.config = config
        self.equipment_list = list(self.components['equipment'].keys())
        self.equipment_count = len(self.equipment_list)
        self.chunk_size = int(ray_rate * self.equipment_count)
       
    def get_solutions(self):
        ray_instances = []
        for chunk in range(0, self.equipment_count, self.chunk_size):
            _components = self.components.copy()
            _components['equipment'] = {k : v for k, v in self.components['equipment'] if k in self.equipment_list[chunk:chunk + self.chunk_size]}
            ray_instances.append(solve.remote(dict_to_building(b.to_dict()), components, config))
            solver = ConstraintSolver(self.building, _components, config=self.config)
            
            
            
            
            solutions, costs = solver.get_solutions()   
        
        
        if len(self.solutions) == 0 or always_recalc:
            self.solutions = self.problem.getSolutions()
            self.cached_solutions.save()
            self.costs = [self.calc_solution_costs(s) for s in self.solutions]
        print(f"solutions: {len(self.solutions)}, cahed: {len(self.cached_solutions.storage)}")
        return self.solutions, self.costs
        #return sorted(self.solutions, key=self.calc_solution_costs)