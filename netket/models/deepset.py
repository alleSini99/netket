from collections.abc import Callable
from typing import TYPE_CHECKING

import jax
from jax import numpy as jnp
from flax import linen as nn
from netket.utils.types import NNInitFunc, DType
from jax.nn.initializers import (
    zeros,
    ones,
    lecun_normal,
)

import netket.nn as nknn

if TYPE_CHECKING:
    from netket.experimental.hilbert import ContinuousHilbert


class DeepSetMLP(nn.Module):
    r"""Implements the DeepSets architecture, which is permutation invariant.

    .. math ::

        f(x_1,...,x_N) = \rho\left(\sum_i \phi(x_i)\right)

    that is suitable for the simulation of bosonic.

    The input shape must have an axis that is reshaped to (..., N, D), where we pool over N.

    See DeepSetRelDistance for the bosonic wave function ansatz in
    https://arxiv.org/abs/1703.06114
    """

    features_phi: int | tuple[int, ...] | None = None
    """
    Number of features in each layer for phi network.
    When features_phi is None, no phi network is created.
    """
    features_rho: int | tuple[int, ...] | None = None
    """
    Number of features in each layer for rho network.
    Should not include the final layer of dimension 1, which is included automatically.
    When features_rho is None, a single layer MLP with output 1 is created.
    """

    param_dtype: DType = jnp.float64
    """The dtype of the weights."""

    hidden_activation: Callable | None = jax.nn.gelu
    """The nonlinear activation function between hidden layers."""
    output_activation: Callable | None = None
    """The nonlinear activation function at the output layer."""

    pooling: Callable = jnp.sum
    """The pooling operation to be used after the phi-transformation"""

    use_bias: bool = True
    """if True uses a bias in all layers."""

    kernel_init: NNInitFunc = lecun_normal()
    """Initializer for the Dense layer matrix"""
    bias_init: NNInitFunc = zeros
    """Initializer for the hidden bias"""
    precision: jax.lax.Precision | None = None
    """numerical precision of the computation see :class:`jax.lax.Precision` for details."""

    @nn.compact
    def __call__(self, input):
        features_rho = _process_features_rho(self.features_rho)
        ds = nknn.blocks.DeepSetMLP(
            features_phi=self.features_phi,
            features_rho=features_rho,
            param_dtype=self.param_dtype,
            hidden_activation=self.hidden_activation,
            output_activation=self.output_activation,
            pooling=self.pooling,
            use_bias=self.use_bias,
            kernel_init=self.kernel_init,
            bias_init=self.bias_init,
            precision=self.precision,
        )
        x = ds(input)
        x = x.squeeze(-1)
        return x


def _process_features_rho(features_input):
    if features_input is None:
        return (1,)
    elif isinstance(features_input, int):
        return (features_input, 1)
    else:
        if not hasattr(features_input, "__len__"):
            raise ValueError("features_rho must be a sequence of integers")
        return (
            *tuple(features_input),
            1,
        )


class DeepSetRelDistance(nn.Module):
    r"""Implements an equivariant version of the DeepSets architecture
    given by (https://arxiv.org/abs/1703.06114)

    .. math ::

        f(x_1,...,x_N) = \rho\left(\sum_i \phi(x_i)\right)

    that is suitable for the simulation of periodic systems.
    Additionally one can add a cusp condition by specifying the
    asymptotic exponent.
    For helium the Ansatz reads (https://arxiv.org/abs/2112.11957):

    .. math ::

        \psi(x_1,...,x_N) = \rho\left(\sum_i \phi(d_{\sin}(x_i,x_j))\right) \cdot \exp\left[-\frac{1}{2}\left(b/d_{\sin}(x_i,x_j)\right)^5\right]

    """

    hilbert: "ContinuousHilbert"
    """The hilbert space defining the periodic box where this ansatz is defined."""

    layers_phi: int
    """Number of layers in phi network."""
    layers_rho: int
    """Number of layers in rho network."""

    features_phi: tuple | int
    """Number of features in each layer for phi network."""
    features_rho: tuple | int
    """
    Number of features in each layer for rho network.
    If specified as a list, the last layer must have 1 feature.
    """

    cusp_exponent: int | None = None
    """exponent of Katos cusp condition"""

    param_dtype: DType = jnp.float64
    """The dtype of the weights."""

    activation: Callable | None = jax.nn.gelu
    """The nonlinear activation function between hidden layers."""
    output_activation: Callable | None = None
    """The nonlinear activation function at the output layer."""

    pooling: Callable = jnp.sum
    """The pooling operation to be used after the phi-transformation"""

    use_bias: bool = True
    """if True uses a bias in all layers."""

    kernel_init: NNInitFunc = lecun_normal()
    """Initializer for the Dense layer matrix"""
    bias_init: NNInitFunc = zeros
    """Initializer for the hidden bias"""
    params_init: NNInitFunc = ones
    """Initializer for the parameter in the cusp"""

    def setup(self):
        if not all(self.hilbert.geometry.pbc):
            raise ValueError(
                "The DeepSetRelDistance model only works with "
                "hilbert spaces with periodic boundary conditions "
                "among all directions."
            )

        features_phi = self.features_phi
        if isinstance(features_phi, int):
            features_phi = [features_phi] * self.layers_phi
        features_phi = tuple(features_phi)

        check_features_length(features_phi, self.layers_phi, "phi")

        features_rho = self.features_rho
        if isinstance(features_rho, int):
            features_rho = [features_rho] * (self.layers_rho - 1) + [1]
        features_rho = tuple(features_rho)

        check_features_length(features_rho, self.layers_rho, "rho")
        assert features_rho[-1] == 1

        self.deepset = DeepSetMLP(
            features_phi,
            features_rho,
            param_dtype=self.param_dtype,
            hidden_activation=self.activation,
            output_activation=self.output_activation,
            pooling=self.pooling,
            use_bias=self.use_bias,
            kernel_init=self.kernel_init,
            bias_init=self.bias_init,
        )

    def distance(self, x, sdim, L):
        n_particles = x.shape[0] // sdim
        x = x.reshape(-1, sdim)

        dis = -x[jnp.newaxis, :, :] + x[:, jnp.newaxis, :]

        dis = dis[jnp.triu_indices(n_particles, 1)]
        dis = L[jnp.newaxis, :] / 2.0 * jnp.sin(jnp.pi * dis / L[jnp.newaxis, :])
        return dis

    @nn.compact
    def __call__(self, x):
        batch_shape = x.shape[:-1]
        param = self.param("cusp", self.params_init, (1,), self.param_dtype)

        L = jnp.array(self.hilbert.domain)
        sdim = L.size

        d = jax.vmap(self.distance, in_axes=(0, None, None))(x, sdim, L)
        dis = jnp.linalg.norm(d, axis=-1)

        cusp = 0.0
        if self.cusp_exponent is not None:
            cusp = -0.5 * jnp.sum(param / dis**self.cusp_exponent, axis=-1)

        y = (d / L[jnp.newaxis, :]) ** 2

        y = self.deepset(y)

        return (y + cusp).reshape(*batch_shape)


def check_features_length(features, n_layers, name):
    if len(features) != n_layers:
        raise ValueError(
            f"The number of {name} layers ({n_layers}) does not match "
            f"the length of the features list ({len(features)})."
        )
