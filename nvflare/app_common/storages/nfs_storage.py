# Copyright (c) 2021-2022, NVIDIA CORPORATION.  All rights reserved.
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

from asyncio.subprocess import STDOUT
import inspect
import os
import pickle
import shutil
import subprocess
from sys import stderr, stdout
import time
from functools import wraps
from typing import ByteString, List, Tuple

from nvflare.apis.storage import StorageSpec


def validate_class_methods_args(cls):
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if name != "__init_subclass__":
            setattr(cls, name, validate_args(method))
    return cls


def validate_args(method):
    signature = inspect.signature(method)

    @wraps(method)
    def wrapper(*args, **kwargs):
        bound_arguments = signature.bind(*args, **kwargs)
        for name, value in bound_arguments.arguments.items():
            annotation = signature.parameters[name].annotation
            if not (annotation is inspect.Signature.empty or isinstance(value, annotation)):
                raise TypeError(
                    "argument '{}' of {} must be {} but got {}".format(name, method, annotation, type(value))
                )
        return method(*args, **kwargs)

    return wrapper


@validate_class_methods_args
class NFSStorage(StorageSpec):
    def __init__(self, server_ip, file_system, mount_point):
        self.mounted = False
        ps = subprocess.Popen(["mnt", "-t", "nfs", server_ip + ":" + file_system, mount_point], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = ps.communicate()
        print(stdout)
        print(stderr)

    def _write(self, path: str, content):
        try:
            with open(path + "_tmp", "wb") as f:
                f.write(pickle.dumps(content))
                f.flush()
                os.fsync(f.fileno())
            if os.path.isfile(path):
                os.remove(path)
        except Exception as e:
            raise IOError("failed to write content: {}".format(e))

        os.rename(path + "_tmp", path)

    def _read(self, path: str) -> object:
        try:
            with open(path, "rb") as f:
                content = pickle.load(f)
        except Exception as e:
            raise IOError("failed to read content: {}".format(e))

        return content

    def _object_exists(self, uri: str):
        data_exists = os.path.isfile(os.path.join(uri, "data"))
        meta_exists = os.path.isfile(os.path.join(uri, "meta"))
        return all((os.path.isabs(uri), os.path.isdir(uri), data_exists, meta_exists))

    def create_object(self, uri: str, data: ByteString, meta: dict, overwrite_existing: bool = False):
        """Create a new object or update an existing object

        Args:
            uri: URI of the object
            data: content of the object
            meta: meta info of the object
            overwrite_existing: whether to overwrite the object if already exists

        Returns:

        Raises exception when:

        - invalid URI specification
        - invalid args
        - object already exists and overwrite_existing is False
        - error creating the object

        Examples of URI:

        /state/engine/...
        /runs/approved/covid_exam.3
        /runs/pending/splee_seg.1

        """
        if self._object_exists(uri) and not overwrite_existing:
            raise Exception("object {} already exists and overwrite_existing is False".format(uri))

        if not os.path.isabs(uri):
            raise Exception("uri {} is not an absolute path".format(uri))

        data_path = os.path.join(uri, "data")
        meta_path = os.path.join(uri, "meta")

        self._write(data_path + "_tmp", data)
        self._write(meta_path, meta)
        os.rename(data_path + "_tmp", data_path)

    def update_meta(self, uri: str, meta: dict, replace: bool):
        """Update the meta info of the specified object

        Args:
            uri: URI of the object
            meta: value of new meta info
            replace: whether to replace the current meta completely or partial update

        Returns:

        Raises exception when:

        - no such object
        - invalid args
        - error updating the object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        if replace:
            self._write(os.path.join(uri, "meta"), meta)
        else:
            prev_meta = self.get_meta(uri)
            prev_meta.update(meta)
            self._write(os.path.join(uri, "meta"), prev_meta)

    def update_data(self, uri: str, data: ByteString):
        """Update the data info of the specified object

        Args:
            uri: URI of the object
            data: value of new data

        Returns:

        Raises exception when:

        - no such object
        - invalid args
        - error updating the object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        self._write(os.path.join(uri, "data"), data)

    def list_objects(self, dir_path: str) -> List[str]:
        """List all objects in the specified path.

        Args:
            path: the path to the objects

        Returns: list of URIs of objects

        """
        if os.path.isdir(dir_path):
            return [
                os.path.join(dir_path, obj)
                for obj in os.listdir(dir_path)
                if self._object_exists(os.path.join(dir_path, obj))
            ]

    def get_meta(self, uri: str) -> dict:
        """Get user defined meta info of the specified object

        Args:
            uri: URI of the object

        Returns: meta info of the object.

        Raises exception when:

        - no such object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        return self._read(os.path.join(uri, "meta"))

    def get_full_meta(self, uri: str) -> dict:
        """Get full meta info of the specified object

        Args:
            uri: URI of the object

        Returns: meta info of the object.

        Raises exception when:

        - no such object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        return self.get_meta(uri)

    def get_data(self, uri: str) -> bytes:
        """Get data of the specified object

        Args:
            uri: URI of the object

        Returns: data of the object.

        Raises exception when:

        - no such object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        return self._read(os.path.join(uri, "data"))

    def get_detail(self, uri: str) -> Tuple[dict, bytes]:
        """Get both data and meta of the specified object

        Args:
            uri: URI of the object

        Returns: meta info and data of the object.

        Raises exception when:

        - no such object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        return self.get_meta(uri), self.get_data(uri)

    def delete_object(self, uri: str):
        """Delete specified object

        Args:
            uri: URI of the object

        Returns:

        Raises exception when:

        - no such object

        """
        if not self._object_exists(uri):
            raise Exception("object {} does not exist".format(uri))

        shutil.rmtree(uri)