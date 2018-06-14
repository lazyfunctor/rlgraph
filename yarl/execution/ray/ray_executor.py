# Copyright 2018 The YARL-Project, All Rights Reserved.
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
# ==============================================================================

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from six.moves import xrange
import logging
from yarl import get_distributed_backend
from yarl.agents import Agent
from yarl.envs import Environment

if get_distributed_backend() == "ray":
    import ray


class RayExecutor(object):
    """
    Abstract distributed Ray executor.

    A Ray executor implements a specific distributed learning semantic by delegating
    distributed state management and execution to the Ray execution engine.

    """
    def __init__(self, cluster_spec):
        """

        Args:
            cluster_spec (dict): Contains all information necessary to set up and execute
                agents on a Ray cluster.
        """
        self.logger = logging.getLogger(__name__)
        self.cluster_spec = cluster_spec

    def ray_init(self):
        """
        Connects to a Ray cluster or starts one if none exists.
        """
        ray.init(
            redis_address=self.cluster_spec['redis_host'],
            num_cpus=self.cluster_spec['ray_num_cpus'],
            num_gpus=self.cluster_spec['ray_num_gpus']
        )

    def create_remote_workers(self, cls, num_actors, *args):
        """
        Creates Ray actors for remote execution.
        Args:
            cls (RayWorker): Actor class, must be an instance of RayWorker.
            num_actors (int): Num
            *args (any): Arguments for RayWorker class.
        Returns:
            list: Remote Ray actors.
        """
        return [cls.remote(args) for _ in xrange(num_actors)]

    def setup_execution(self):
        """
        Creates and initializes all remote agents on the Ray cluster.
        """
        raise NotImplementedError

    def execute_workload(self, workload):
        """
        Executes a given workload according to a specific distributed update semantic.

        Args:
            workload (dict): Dict specifying workload by describing environments, number of steps
                or episodes to execute, and termination conditions.

        Returns:
            dict: Summary statistics of distributed workload.
        """
        raise NotImplementedError

    @staticmethod
    def build_agent_from_config(agent_config):
        """
        Builds agent without using from_spec as Ray cannot handle kwargs correctly
        at the moment.

        Args:
            agent_config (dict): Agent config. Must contain 'type' field to lookup constructor.

        Returns:
            Agent: YARL agent object.
        """
        agent_cls = Agent.__lookup_classes__.get(agent_config.pop('type'))
        return agent_cls(**agent_config)

    @staticmethod
    def build_env_from_config(env_spec):
        """
        Builds environment without using from_spec as Ray cannot handle kwargs correctly
        at the moment.

        Args:
            env_spec (dict): Environment specificaton. Must contain 'type' field to lookup constructor.

        Returns:
            Environment: Env object.
        """
        env_cls = Environment.__lookup_classes__.get(env_spec['type'])
        return env_cls(env_spec['gym_env'])
