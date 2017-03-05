import numpy as np
from rl.hyperoptimizer.base_hyperoptimizer import HyperOptimizer
from rl.util import PROBLEMS


class RandomSearch(HyperOptimizer):

    '''
    Random Search by sampling on hysphere around a search path
    algo:
    1. init x a random position in space
    2. until termination (max_eval or fitness, e.g. solved all), do:
        2.1 sample new pos some radius away: next_x = x + r
        2.2 if f(next_x) > f(x) then set x = next_x

    Extra search memory units:
    - search_path
    - best_point

    save for experiment resume:
    - search_path
    - best_point
    - param_search_list
    '''

    def set_keys(self, **kwargs):
        self.REQUIRED_GLOBAL_VARS = [
            'experiment_spec',
            'experiment_id_override',
            'times',
            'max_evals'
        ]
        super(RandomSearch, self).set_keys(**kwargs)

    # calculate the constant radius needed to traverse unit cube
    def cube_traversal_radius(self):
        traversal_diameter = 1/np.power(self.max_evals,
                                        1/self.search_dim)
        traversal_radius = traversal_diameter/2
        return traversal_radius

    def decay_radius(self):
        '''
        future implementation, start of half cube for diameter
        (so 1/4 for radius), then decay
        '''
        return

    @classmethod
    def sample_hypersphere(cls, dim, r=1):
        '''Marsaglia algo for sampling uniformly on a hypersphere'''
        v = np.random.randn(dim)
        v = v * r / np.linalg.norm(v)
        return v

    def sample_cube(self):
        return np.random.rand(self.search_dim)

    def sample_r(self):
        return self.sample_hypersphere(
            self.search_dim, self.search_radius)

    # biject [0, 1] to [x_min, x_max]
    @classmethod
    def biject_continuous(cls, norm_val, x_min, x_max):
        return norm_val*(x_max - x_min) + x_min

    # biject [0, 1] to x_list = [a, b, c, ...] by binning
    def biject_discrete(self, norm_val, x_list):
        list_len = len(x_list)
        inds = np.arange(list_len)
        cont_val = self.biject_continuous(norm_val, 0, list_len)
        ind = np.digitize(cont_val, inds) - 1
        return x_list[ind]

    # biject one dimension: [0, 1] to a param_range val
    def biject_dim(self, norm_val, dim_spec):
        if isinstance(dim_spec, list):  # discrete
            return self.biject_discrete(norm_val, dim_spec)
        else:  # cont
            return self.biject_continuous(
                norm_val, dim_spec['min'], dim_spec['max'])
        return

    # biject a vector on unit cube into a param in param_space
    def biject_param(self, v):
        param = {}
        for i, param_key in enumerate(self.param_range_keys):
            dim_spec = self.param_range[param_key]
            param[param_key] = self.biject_dim(v[i], dim_spec)
        return param

    def init_search(self):
        '''
        Initialize the random search internal variables
        '''
        self.num_of_trials = self.max_evals
        self.search_dim = len(self.param_range_keys)
        self.search_radius = self.cube_traversal_radius()
        self.search_path = []
        self.best_point = {
            'trial_num': None,
            'param': None,
            'x': self.sample_cube(),
            'fitness_score': float('-inf'),
        }
        problem = PROBLEMS.get(self.experiment_spec['problem'])
        self.ideal_fitness_score = 0.5 * \
            problem['SOLVED_MEAN_REWARD']/problem['MAX_EPISODES']

    def search(self):
        '''
        algo step 2.1 sample new pos some radius away: next_x = x + r
        update search_path and param_search_list
        '''
        next_x = self.best_point['x'] + self.sample_r()
        next_param = self.biject_param(next_x)
        self.search_path.append(next_x)
        self.param_search_list.append(next_param)

    def update_search(self):
        '''
        algo step 2.2 if f(next_x) > f(x) then set x = next_x
        invoked right after the latest run_trial()
        update self.best_point
        '''
        if self.next_trial_num < self.PARALLEL_PROCESS_NUM:  # first runs yet
            return
        assert len(self.experiment_data) > 0, \
            'self.experiment_data must not be empty for update_search'
        x = self.search_path[-1]
        trial_data = self.experiment_data[-1]
        trial_num, param, fitness_score = self.get_fitness(trial_data)

        if fitness_score > self.best_point['fitness_score']:
            self.best_point = {
                'trial_num': trial_num,
                'param': param,
                'x': x,
                'fitness_score': fitness_score,
            }

    def satisfy_fitness(self):
        '''
        break on the first strong solution
        '''
        if self.next_trial_num < self.PARALLEL_PROCESS_NUM:
            return False
        else:
            return self.best_point['fitness_score'] > self.ideal_fitness_score

    def to_terminate(self):
        return (self.next_trial_num >= self.max_evals or
                self.satisfy_fitness())
