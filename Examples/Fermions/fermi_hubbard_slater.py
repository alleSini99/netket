import netket as nk
import netket.experimental as nkx

import numpy as np
import matplotlib.pyplot as plt
import json

L = 2  # take a 2x2 lattice
D = 2
t = 1  # tunneling/hopping
U = 0.01  # coulomb

# create the graph our fermions can hop on
g = nk.graph.Hypercube(length=L, n_dim=D, pbc=True)
n_sites = g.n_nodes

# create a hilbert space with 2 up and 2 down spins
hi = nk.hilbert.SpinOrbitalFermions(n_sites, s=1 / 2, n_fermions_per_spin=(2, 2))


# create an operator representing fermi hubbard interactions
# -t (i^ j + h.c.) + U (i^ i j^ j)
ham = nkx.operator.FermiHubbardJax(hi, t=t, U=U, graph=g)

# metropolis exchange moves fermions around according to a graph
# the physical graph has LxL vertices, but the computational basis defined by the
# hilbert space contains (2s+1)*L*L occupation numbers
# by taking a disjoint copy of the lattice, we can
# move the fermions around independently for both spins
# and therefore conserve the number of fermions with up and down spin

# g.n_nodes == L*L --> disj_graph == 2*L*L
# this is handled by netket by passing the keyword spin_symmetric=True
sa = nk.sampler.MetropolisFermionHop(
    hi, graph=g, n_chains=16, spin_symmetric=True, sweep_size=64
)

# since the hilbert basis is a set of occupation numbers, we can take a general RBM
# we take complex parameters, since it learns sign structures more easily, and for even fermion number, the wave function might be complex
ma = nk.models.Slater2nd(hi, param_dtype=complex)
vs = nk.vqs.MCState(sa, ma, n_discard_per_chain=10, n_samples=512)

# we will use sgd with Stochastic Reconfiguration
opt = nk.optimizer.Sgd(learning_rate=0.01)
sr = nk.optimizer.SR(diag_shift=0.1, holomorphic=True)

gs = nk.driver.VMC(ham, opt, variational_state=vs, preconditioner=sr)

# now run the optimization
# first step will take longer in order to compile
exp_name = "fermions_test"
gs.run(500, out=exp_name)

############## plot #################

ed_energies = np.linalg.eigvalsh(ham.to_dense())

with open(f"{exp_name}.log") as f:
    data = json.load(f)

x = data["Energy"]["iters"]
y = data["Energy"]["Mean"]["real"]

# plot the energy levels
plt.axhline(ed_energies[0], color="red", label="E0")
for e in ed_energies[1:]:
    plt.axhline(e, color="black")
plt.semilogy(x, y - ed_energies[0], color="red", label="VMC")
plt.xlabel("step")
plt.ylabel("E")
plt.show()
