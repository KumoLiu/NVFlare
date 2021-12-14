# Copyright (c) 2021, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class ModelDescriptor:
    def __init__(self, name: str, location: str, model_format: str, props: dict = None) -> None:
        """
        The class to describe the model.
        Args:
            name: model name
            location: model location
            model_format: model format
            props: additional properties of the model
        """
        super().__init__()
        self.name = name
        self.location = location
        self.model_format = model_format
        self.props = props