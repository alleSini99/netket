# Copyright 2021 The NetKet Authors - All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
from collections.abc import Callable
from collections.abc import Hashable

from netket.jax import canonicalize_dtypes
from netket.utils import struct
from netket.utils.types import DType, PyTree, Array

from netket.hilbert import AbstractHilbert
from netket.operator import AbstractOperator


class ContinuousOperator(AbstractOperator, struct.Pytree):
    r"""This class is the abstract base class for operators defined on a
    continuous Hilbert space. Users interested in implementing new
    quantum Operators for continuous Hilbert spaces should subclass
    `ContinuousOperator` and implement its interface.
    """

    _hilbert: AbstractHilbert = struct.static_field()
    _dtype: DType = struct.static_field()

    def __init__(self, hilbert: AbstractHilbert, dtype: DType | None = None):
        r"""
        Constructs the continuous operator acting on the given hilbert space and
        with a certain data type.

        Args:
            hilbert: The underlying Hilbert space on which the operator is defined
            dtype: Data type of the operator, which is used to infer the dtype of
                expectation values
        """
        dtype = canonicalize_dtypes(float, dtype=dtype)
        self._dtype = dtype
        super().__init__(hilbert)

    @property
    def dtype(self) -> DType:
        return self._dtype

    @abc.abstractmethod
    def _expect_kernel(
        self,
        logpsi: Callable,
        params: PyTree,
        x: Array,
    ) -> Array:
        r"""This method defines the action of the local operator on a given quantum state
        `logpsi` for a given configuration `x`.
        :math:`O_{loc}(x) =  \frac{\bra{x}O{\ket{\psi}}{\bra{x}\ket{\psi}}`
        This method is executed inside of a `jax.jit` block.

        .. note::
            The operator itself must be a Pytree.

        Args:
            logpsi: variational state
            params: parameters for the variational state
            x: a sample of particle positions
        """

    @abc.abstractproperty
    def _attrs(self) -> tuple[Hashable, ...]:
        """This must return a tuple of (hashable) attributes used to compare two operators of
        the same type and that is hashed to compute the hash of the operator.

        To hash arrays you can return them as `nk.utils.HashableArray`.
        """

    @struct.property_cached(pytree_ignore=True)
    def _hash(self) -> int:
        return hash((type(self), self._attrs))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other) -> bool:
        if isinstance(other, type(self)):
            return self._attrs == other._attrs
        return False

    def __add__(self, other):
        if isinstance(self, ContinuousOperator) and isinstance(
            other, ContinuousOperator
        ):
            from netket.operator import SumOperator

            return SumOperator(self, other)
        else:
            return NotImplemented  # pragma: no cover

    def __rmul__(self, other):
        if isinstance(self, ContinuousOperator) and isinstance(other, float):
            return self * other
        else:
            return NotImplemented  # pragma: no cover

    def __mul__(self, other):
        if isinstance(self, ContinuousOperator) and isinstance(other, float):
            from netket.operator import SumOperator

            return SumOperator(self, coefficients=other)
        else:
            return NotImplemented  # pragma: no cover

    def __sub__(self, other):
        if isinstance(other, ContinuousOperator):
            return self + (-other)
        else:
            return NotImplemented  # pragma: no cover

    def __neg__(self):
        return -1.0 * self
