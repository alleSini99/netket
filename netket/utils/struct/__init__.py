# Copyright 2020, 2021 The NetKet Authors - All rights reserved.
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

# flake8: noqa: F401

from netket.utils.struct.fields import (
    field,
    static_field,
    property_cached,
    Uninitialized,
)

from netket.utils.struct.dataclass import dataclass

from netket.utils.struct.pytree import Pytree

from netket.utils.struct.pytree_serialization_sharding import ShardedFieldSpec
