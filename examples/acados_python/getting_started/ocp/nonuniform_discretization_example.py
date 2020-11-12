#
# Copyright 2019 Gianluca Frison, Dimitris Kouzoupis, Robin Verschueren,
# Andrea Zanelli, Niels van Duijkeren, Jonathan Frey, Tommaso Sartor,
# Branimir Novoselnik, Rien Quirynen, Rezart Qelibari, Dang Doan,
# Jonas Koenemann, Yutao Chen, Tobias Schöls, Jonas Schlagenhauf, Moritz Diehl
#
# This file is part of acados.
#
# The 2-Clause BSD License
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.;
#

import sys, json, os
sys.path.insert(0, '../common')

from acados_template import AcadosOcp, AcadosOcpSolver, acados_dae_model_json_dump
from pendulum_model import export_pendulum_ode_model
import numpy as np
import scipy.linalg
from utils import plot_pendulum

# create ocp object to formulate the OCP
ocp = AcadosOcp()

# set model
model = export_pendulum_ode_model()
ocp.model = model

integrator_type = 'IRK' # ERK, IRK, GNSF

if integrator_type == 'GNSF':
    acados_dae_model_json_dump(model)
    # structure detection in Matlab/Octave -> produces 'pendulum_ode_gnsf_functions.json'
    status = os.system('octave detect_gnsf_from_json.m')
    # load gnsf from json
    with open(model.name + '_gnsf_functions.json', 'r') as f:
        gnsf_dict = json.load(f)
    ocp.gnsf_model = gnsf_dict

Tf = 1.0
nx = model.x.size()[0]
nu = model.u.size()[0]
ny = nx + nu
ny_e = nx
N = 15

# discretization
ocp.dims.N = N
# shooting_nodes = np.linspace(0, Tf, N+1)

N1 = 10
N2 = N - N1

time_steps = .5 * np.concatenate( (( 0.1 * np.ones(N1,)), 0.2 * (np.ones(N2,))))

shooting_nodes = np.zeros((N+1,))
for i in range(len(time_steps)):
    shooting_nodes[i+1] = shooting_nodes[i] + time_steps[i]

# nonuniform discretizations can be defined either by shooting_nodes or time_steps:
ocp.solver_options.shooting_nodes = shooting_nodes
# ocp.solver_options.time_steps = time_steps

# set cost
Q = 2*np.diag([1e3, 1e3, 1e-2, 1e-2])
R = 2*np.diag([1e-2])

ocp.cost.W_e = Q
ocp.cost.W = scipy.linalg.block_diag(Q, R)

ocp.cost.cost_type = 'LINEAR_LS'
ocp.cost.cost_type_e = 'LINEAR_LS'

ocp.cost.Vx = np.zeros((ny, nx))
ocp.cost.Vx[:nx,:nx] = np.eye(nx)

Vu = np.zeros((ny, nu))
Vu[4,0] = 1.0
ocp.cost.Vu = Vu

ocp.cost.Vx_e = np.eye(nx)

ocp.cost.yref  = np.zeros((ny, ))
ocp.cost.yref_e = np.zeros((ny_e, ))

# set constraints
Fmax = 80
ocp.constraints.lbu = np.array([-Fmax])
ocp.constraints.ubu = np.array([+Fmax])

x0 = np.array([0.0, np.pi, 0.0, 0.0])
ocp.constraints.x0 = x0
ocp.constraints.idxbu = np.array([0])

ocp.solver_options.qp_solver = 'PARTIAL_CONDENSING_HPIPM' # FULL_CONDENSING_QPOASES
ocp.solver_options.hessian_approx = 'GAUSS_NEWTON'
ocp.solver_options.integrator_type = integrator_type
ocp.solver_options.print_level = 0
ocp.solver_options.nlp_solver_type = 'SQP' # SQP_RTI, SQP

# set prediction horizon
ocp.solver_options.tf = Tf
ocp.solver_options.initialize_t_slacks = 1

ocp_solver = AcadosOcpSolver(ocp, json_file = 'acados_ocp.json')

simX = np.ndarray((N+1, nx))
simU = np.ndarray((N, nu))

ocp_solver.options_set("step_length", 0.99999)
ocp_solver.options_set("globalization", "fixed_step") # fixed_step, merit_backtracking

# initialize solver
for i in range(N):
    ocp_solver.set(i, "x", x0)
status = ocp_solver.solve()

if status not in [0, 2]:
    raise Exception('acados returned status {}. Exiting.'.format(status))

# get primal solution
for i in range(N):
    simX[i,:] = ocp_solver.get(i, "x")
    simU[i,:] = ocp_solver.get(i, "u")
simX[N,:] = ocp_solver.get(N, "x")

print("inequality multipliers at stage 1")
print(ocp_solver.get(1, "lam")) # inequality multipliers at stage 1
print("slack values at stage 1")
print(ocp_solver.get(1, "t")) # slack values at stage 1
print("multipliers of dynamic conditions between stage 1 and 2")
print(ocp_solver.get(1, "pi")) # multipliers of dynamic conditions between stage 1 and 2

# initialize ineq multipliers and slacks at stage 1
ocp_solver.set(1, "lam", np.zeros(2,))
ocp_solver.set(1, "t", np.zeros(2,))

ocp_solver.print_statistics() # encapsulates: stat = ocp_solver.get_stats("statistics")

# print("simU", simU)
# print("simX", simX)

plot_pendulum(shooting_nodes, Fmax, simU, simX, latexify=False)
