# A simple FSI problem involving a hyperelastic obstruction in a
# Navier-Stokes flow field. Lessons learnt from this exercise will be
# used to construct an FSI class in the future.


from cbc.flow import *
from cbc.twist import *
from numpy import array

plot_solution = True

# Constants related to the geometry of the channel and the obstruction
channel_length  = 3.0
channel_height  = 1.0
structure_left  = 1.4
structure_right = 1.6
structure_top   = 0.5
nx = 60
ny = 20
    
# Create the complete mesh
mesh = Rectangle(0.0, 0.0, channel_length, channel_height, nx, ny)

# Define structure subdomain
class Structure(SubDomain):
    def inside(self, x, on_boundary):
        return (x[0] >= structure_left) and (x[0] <= structure_right) \
            and (x[1] <= structure_top)
    
# Create subdomain markers (0: fluid 1: structure)
sub_domains = MeshFunction("uint", mesh, mesh.topology().dim())
sub_domains.set_all(0)
structure = Structure()
structure.mark(sub_domains, 1)

# Extract submeshes for fluid and structure
Omega_F = SubMesh(mesh, sub_domains, 0)
Omega_S = SubMesh(mesh, sub_domains, 1)
omega_F0 = Mesh(Omega_F)
omega_F1 = Mesh(Omega_F)

# Extract matching indices for fluid and structure
structure_to_fluid = compute_vertex_map(Omega_S, Omega_F)

# Extract matching indices for fluid and structure
structure_indices = array([i for i in structure_to_fluid.iterkeys()])
fluid_indices = array([i for i in structure_to_fluid.itervalues()])

# Define inflow boundary
def inflow(x):
    return x[0] < DOLFIN_EPS and x[1] > DOLFIN_EPS and x[1] < channel_height - DOLFIN_EPS

# Define outflow boundary
def outflow(x):
    return x[0] > channel_length - DOLFIN_EPS and x[1] > DOLFIN_EPS and x[1] < channel_height - DOLFIN_EPS

# Define noslip boundary
def noslip(x, on_boundary):
    return on_boundary and not inflow(x) and not outflow(x)

# Parameters
t = 0
T = 10.0
dt = 0.0025
tol = 1e-3

P1F = VectorFunctionSpace(Omega_F, "CG", 1)

# Define fluid problem
class FluidProblem(NavierStokes):
    
    def mesh(self):
        return omega_F1

    def viscosity(self):
        return 0.005
    
#     def end_time(self):
#         return 0.5
    
#    def mesh_displacement(self):
#        self.X0  =  MeshCoordinates(mesh)
#        self.X1  =  MeshCoordinates(mesh)
#        self.m_d =  X0 - X1
#        return self.m_d
        
#    def update_mesh_displacement(self, X1):
#         self.X0.assign(self.X1)
#         return self.X1

    def mesh_velocity(self, V):
        self.w = Function(V)
        return self.w

    def update_mesh(self):
        # Do something with self.w
        # Change w.vector()
        print "Calling update_mesh but doing nothing"
        pass
        
    def boundary_conditions(self, V, Q):
        
        # Create no-slip boundary condition for velocity
        bcu = DirichletBC(V, Constant(V.mesh(), (0, 0)), noslip)
        
        # FIXME: Anders fix DirichletBC to take int or float instead of Constant
        
        # Create inflow and outflow boundary conditions for pressure
        bcp0 = DirichletBC(Q, Constant(Q.mesh(), 1), inflow)
        bcp1 = DirichletBC(Q, Constant(Q.mesh(), 0), outflow)

        return [bcu], [bcp0, bcp1]

    def time_step(self):
        return dt

    def __str__(self):
        return "Pressure driven channel (2D) with an obstructure"

# Define struture problem
class StructureProblem(Hyperelasticity):

    def __init__(self):
        Hyperelasticity.__init__(self)
        
        # Define basis function for transfer of stress
        self.V_F = VectorFunctionSpace(Omega_F, "CG", 1)
        self.v_F = TestFunction(self.V_F)
        self.N_F = FacetNormal(Omega_F)
    
    def init(self, scalar, vector):
        self.scalar = scalar
        self.vector = vector
            
    def mesh(self):
        return Omega_S

    def v_F(self):
        return TestFunction(self.fluid_mesh(), "CG", 1)

    def dirichlet_conditions(self, vector):
        fix = Expression(("0.0", "0.0"), V = vector)
        return [fix]
 
    def dirichlet_boundaries(self):
        #FIXME: Figure out how to use the constants above in the
        #following boundary definitions
        bottom = "x[1] == 0.0 && x[0] >= 1.4 && x[0] <= 1.6"
        return [bottom]

    def update_fluid_load(self, Sigma_F):

        # Assemble traction on fluid domain
        print "Assembling traction on fluid domain"
        L_F = dot(self.v_F, dot(Sigma_F, self.N_F))*ds
        B_F = assemble(L_F)
        
        # Transfer values to structure domain
        print "Transferring values to structure domain"
        
        # Add contribution from fluid vector to structure 
        B_S = Vector(self.vector.dim())
        B_S_array = B_S.array()
        B_F_array = B_F.array()
        B_S_array[structure_indices] += B_F_array[fluid_indices]
        B_S[:] = B_S_array

        # This is not how it should be done. It's completely crazy
        # but it gives an effect in the right direction...
        self.fluid_load.vector()[:] = -B_S_array

        # What we should really do is send B_S to Harish!
        
    def neumann_conditions(self, vector):
        self.fluid_load = Function(vector)#0
        return [self.fluid_load]

    def neumann_boundaries(self):
        # Return the entire structure boundary as the Neumann
        # boundary, knowing that the Dirichlet boundary will overwrite
        # it at the bottom
        return["on_boundary"]

    def material_model(self):
        mu       = 3.8461
        lmbda    = 5.76
        material = StVenantKirchhoff([mu, lmbda])
        return material

    def time_step(self):
        return dt

    def __str__(self):
        return "The structure problem"

fluid = FluidProblem()
structure = StructureProblem()

U_M = Function(structure.V_F)


# FIXME: Time step used by solver might not be dt!!!

# Time-stepping
while t < T:

    print "Solving the problem at t = ", str(t)
    print "--------------------------------"
    
    # Fixed point iteration on FSI problem
    r = 2*tol
    while r > tol:
        
        # Solve fluid equation
        u_F, p_F = fluid.step(dt)
       
        # Compute fluid stress tensor
        sigma_F = fluid.cauchy_stress(u_F, p_F)
        Sigma_F = PiolaTransform(sigma_F, U_M)
        
        # Update fluid stress on structure
        structure.update_fluid_load(Sigma_F)
        
        # Solve structure equation
        U_S = structure.step(dt)
        
        # Solve mesh equation
        #fluid_mesh.move(U_S, harmonic)
        
        # Update fluid mesh
        fluid.update_mesh()

        # Plot solutions
        if plot_solution:
            plot(u_F, title="Fluid velocity")
            plot(U_S, title="Structure displacement")

        # Compute residual
        r = tol / 2 # norm(U_S) something

    # Move to next time step
    fluid.update()
    structure.update()

    t += dt

# Hold plot
interactive()
