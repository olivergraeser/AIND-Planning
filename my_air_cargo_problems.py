from aimacode.logic import PropKB
from aimacode.planning import Action
from aimacode.search import (
    Node, Problem,
)
from aimacode.utils import expr
from lp_utils import (
    FluentState, encode_state, decode_state,
)
from my_planning_graph import PlanningGraph

from functools import lru_cache


class AirCargoProblem(Problem):
    def __init__(self, cargos, planes, airports, initial: FluentState, goal: list):
        """

        :param cargos: list of str
            cargos in the problem
        :param planes: list of str
            planes in the problem
        :param airports: list of str
            airports in the problem
        :param initial: FluentState object
            positive and negative literal fluents (as expr) describing initial state
        :param goal: list of expr
            literal fluents required for goal test
        """
        self.state_map = initial.pos + initial.neg
        self.initial_state_TF = encode_state(initial, self.state_map)
        Problem.__init__(self, self.initial_state_TF, goal=goal)
        self.cargos = cargos
        self.planes = planes
        self.airports = airports
        self.actions_list = self.get_actions()

    def get_actions(self):
        """
        This method creates concrete actions (no variables) for all actions in the problem
        domain action schema and turns them into complete Action objects as defined in the
        aimacode.planning module. It is computationally expensive to call this method directly;
        however, it is called in the constructor and the results cached in the `actions_list` property.

        Returns:
        ----------
        list<Action>
            list of Action objects
        """

        # TODO create concrete Action objects based on the domain action schema for: Load, Unload, and Fly
        # concrete actions definition: specific literal action that does not include variables as with the schema
        # for example, the action schema 'Load(c, p, a)' can represent the concrete actions 'Load(C1, P1, SFO)'
        # or 'Load(C2, P2, JFK)'.  The actions for the planning problem must be concrete because the problems in
        # forward search and Planning Graphs must use Propositional Logic

        def load_actions():
            """Create all concrete Load actions and return a list

            :return: list of Action objects
            """
            loads = list()
            for airport in self.airports:
                for plane in self.planes:
                    for cargo in self.cargos:
                        precond_pos = [expr('At({},{})'.format(plane, airport)), expr('At({},{})'.format(cargo, airport))]
                        precond_neg = []
                        effect_pos = [expr('In({},{})'.format(cargo, plane))]
                        effect_neg = [expr('At({},{})'.format(cargo, airport))]
                        loads.append(Action(action=expr('Load({}, {}, {})'.format(cargo, plane, airport)),
                                            precond=(precond_pos, precond_neg),
                                            effect=(effect_pos, effect_neg)))

            return loads

        def unload_actions():
            """Create all concrete Unload actions and return a list

            :return: list of Action objects
            """
            unloads = list()
            for airport in self.airports:
                for plane in self.planes:
                    for cargo in self.cargos:
                        precond_pos = [expr('At({},{})'.format(plane, airport)), expr('In({},{})'.format(cargo, plane))]
                        precond_neg = []
                        effect_pos = [expr('At({},{})'.format(cargo, airport))]
                        effect_neg = [expr('In({},{})'.format(cargo, plane))]
                        unloads.append(Action(action=expr('Unload({}, {}, {})'.format(cargo, plane, airport)),
                                              precond=(precond_pos, precond_neg),
                                              effect=(effect_pos, effect_neg)))

            return unloads

        def fly_actions():
            """Create all concrete Fly actions and return a list

            :return: list of Action objects
            """
            flys = []
            for fr in self.airports:
                for to in self.airports:
                    if fr != to:
                        for p in self.planes:
                            precond_pos = [expr("At({}, {})".format(p, fr)),
                                           ]
                            precond_neg = []
                            effect_add = [expr("At({}, {})".format(p, to))]
                            effect_rem = [expr("At({}, {})".format(p, fr))]
                            fly = Action(expr("Fly({}, {}, {})".format(p, fr, to)),
                                         [precond_pos, precond_neg],
                                         [effect_add, effect_rem])
                            flys.append(fly)
            return flys

        return load_actions() + unload_actions() + fly_actions()

    def actions(self, state: str) -> list:
        def permissible(action, state):
            for precond_pos in action.precond_pos:
                if precond_pos not in decode_state(state, self.state_map).pos:
                    return False
            for precond_neg in action.precond_neg:
                if precond_neg not in decode_state(state, self.state_map).neg:
                    return False
            return True
        """ Return the actions that can be executed in the given state.

        :param state: str
            state represented as T/F string of mapped fluents (state variables)
            e.g. 'FTTTFF'
        :return: list of Action objects
        """
        # TODO implement
        possible_actions = [_ for _ in self.actions_list if permissible(_, state)]
        return possible_actions

    def result(self, state: str, action: Action):
        """ Return the state that results from executing the given
        action in the given state. The action must be one of
        self.actions(state).

        :param state: state entering node
        :param action: Action applied
        :return: resulting state after action
        """
        available_action_strings = ['{}{!s}'.format(_.name, _.args) for _ in self.actions(state=state)]
        action_string = '{}{!s}'.format(action.name, action.args)
        decoded_state = decode_state(state=state, fluent_map=self.state_map)
        new_state = decoded_state
        if action_string in available_action_strings:
            new_state = FluentState([_ for _ in decoded_state.pos if _ not in action.effect_rem] + action.effect_add,
                                    [_ for _ in decoded_state.neg if _ not in action.effect_add] + action.effect_rem)
        else:
            raise Exception('wrong action: {}|{}, allowed_actions (in format <name|args|allowed.name==action.name'
                            '|allowed.args==action.args|allowed==action>:\n{}'
                            .format(action.name, action.args,
                                    '\n'.join('<{}|{}|{}|{}|{}>'.format(_.name, _.args, _.name == action.name,
                                                                        _.args == action.args, _ == action)
                                              for _ in self.actions(state=state))))
        return encode_state(new_state, self.state_map)

    def goal_test(self, state: str) -> bool:
        """ Test the state to see if goal is reached

        :param state: str representing state
        :return: bool
        """
        kb = PropKB()
        kb.tell(decode_state(state, self.state_map).pos_sentence())
        for clause in self.goal:
            if clause not in kb.clauses:
                return False
        return True

    def h_1(self, node: Node):
        # note that this is not a true heuristic
        h_const = 1
        return h_const

    @lru_cache(maxsize=8192)
    def h_pg_levelsum(self, node: Node):
        """This heuristic uses a planning graph representation of the problem
        state space to estimate the sum of all actions that must be carried
        out from the current state in order to satisfy each individual goal
        condition.
        """
        # requires implemented PlanningGraph class
        pg = PlanningGraph(self, node.state)
        pg_levelsum = pg.h_levelsum()
        return pg_levelsum

    @lru_cache(maxsize=8192)
    def h_ignore_preconditions(self, node: Node):
        """This heuristic estimates the minimum number of actions that must be
        carried out from the current state in order to satisfy all of the goal
        conditions by ignoring the preconditions required for an action to be
        executed.
        """
        negative_states = decode_state(node.state, self.state_map).neg
        negative_state_strings = {'{}{!s}'.format(_.op, _.args) for _ in negative_states}
        goal_state_strings = {'{}{!s}'.format(_.op, _.args) for _ in self.goal}
        count = len(negative_state_strings.intersection(goal_state_strings))
        return count


def air_cargo_p1() -> AirCargoProblem:
    cargos = ['C1', 'C2']
    planes = ['P1', 'P2']
    airports = ['JFK', 'SFO']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    neg = [expr('At(C1, JFK)'),
           expr('At(C2, SFO)'),
           expr('At(P1, JFK)'),
           expr('At(P2, SFO)'),
           expr('In(C1, P1)'),
           expr('In(C1, P2)'),
           expr('In(C2, P1)'),
           expr('In(C2, P2)'),
           ]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)


def air_cargo_p2() -> AirCargoProblem:
    cargos = ['C1', 'C2', 'C3']
    planes = ['P1', 'P2', 'P3']
    airports = ['JFK', 'SFO', 'ATL']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, ATL)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           expr('At(P3, ATL)'),
           ]
    total = [expr('At({},{})'.format(cp, l)) for cp in cargos+planes for l in airports] + \
            [expr('In({},{})'.format(c, p)) for c in cargos for p in planes]
    neg = [_ for _ in total if _ not in pos]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C3, SFO)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)


def air_cargo_p3() -> AirCargoProblem:

    cargos = ['C1', 'C2', 'C3', 'C4']
    planes = ['P1', 'P2',]
    airports = ['JFK', 'SFO', 'ATL', 'ORD']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, ATL)'),
           expr('At(C4, ORD)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           ]
    total = [expr('At({},{})'.format(cp, l)) for cp in cargos + planes for l in airports] + \
            [expr('In({},{})'.format(c, p)) for c in cargos for p in planes]
    neg = [_ for _ in total if _ not in pos]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C4, SFO)'),
            expr('At(C3, JFK)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)

def air_cargo_p4    () -> AirCargoProblem:

    cargos = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8']
    planes = ['P1', 'P2', 'P3']
    airports = ['JFK', 'SFO', 'ATL', 'ORD', 'SIN', 'HKG', 'YYZ']
    pos = [expr('At(C1, SFO)'),
           expr('At(C2, JFK)'),
           expr('At(C3, ATL)'),
           expr('At(C4, ORD)'),
           expr('At(C5, ORD)'),
           expr('At(C6, ORD)'),
           expr('At(C7, HKG)'),
           expr('At(C8, SIN)'),
           expr('At(P1, SFO)'),
           expr('At(P2, JFK)'),
           expr('At(P2, YYZ)'),
           ]
    total = [expr('At({},{})'.format(cp, l)) for cp in cargos + planes for l in airports] + \
            [expr('In({},{})'.format(c, p)) for c in cargos for p in planes]
    neg = [_ for _ in total if _ not in pos]
    init = FluentState(pos, neg)
    goal = [expr('At(C1, JFK)'),
            expr('At(C2, SFO)'),
            expr('At(C4, SFO)'),
            expr('At(C3, JFK)'),
            expr('At(C5, HKG)'),
            expr('At(C6, ATL)'),
            expr('At(C7, SIN)'),
            expr('At(C8, JFK)'),
            ]
    return AirCargoProblem(cargos, planes, airports, init, goal)
