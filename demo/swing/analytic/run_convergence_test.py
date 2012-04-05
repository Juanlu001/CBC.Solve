"""This script runs a convergence test for the primal problem of the
analytic test case using uniform refinement in space and time."""

__author__ = "Anders Logg"
__copyright__ = "Copyright (C) 2012 Simula Research Laboratory and %s" % __author__
__license__  = "GNU GPL Version 3 or any later version"

# First added:  2012-03-05
# Last changed: 2012-04-06

from cbc.swing import *

# Set up parameters
p = default_parameters()
p["solve_primal"] = True
p["solve_dual"] = True
p["estimate_error"] = True
p["plot_solution"] = False
p["uniform_timestep"] = True
p["uniform_mesh"] = True
p["initial_timestep"] = 0.01
p["tolerance"] = 1e-8
p["fixedpoint_tolerance"] = 1e-8
p["output_directory"] = "results_analytic_convergence_test"
p["max_num_refinements"] = 10

# Run
run_local("analytic", p, "convergence_test")
