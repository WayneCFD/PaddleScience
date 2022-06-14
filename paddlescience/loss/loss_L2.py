# Copyright (c) 2022 PaddlePaddle Authors. All Rights Reserved.
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

import paddle
import numpy as np
from .loss_base import LossBase, CompFormula
from ..labels import LabelInt


class L2(LossBase):
    """
    L2 loss.

    Parameters:
        p(1 or 2):

            p=1: total loss = eqloss + bcloss + icloss + dataloss.

            p=2: total loss = sqrt(eqloss**2 + bcloss**2 + icloss**2 + dataloss**2)

    Example:
        >>> import paddlescience as psci
        >>> loss = psci.loss.L2()
    """

    def __init__(self, p=1, data_weight=1.0):
        self.norm_p = p
        self.data_weight = data_weight

    # compute loss on one interior 
    # there are multiple pde
    def eq_loss(self, pde, net, input, input_attr, labels, labels_attr, bs):

        cmploss = CompFormula(pde, net)

        # compute outs, jacobian, hessian
        cmploss.compute_outs_der(input, bs)

        # print(input)
        # print(cmploss.outs[0:4,:])

        loss = 0.0
        for i in range(len(pde.equations)):
            formula = pde.equations[i]
            rst = cmploss.compute_formula(formula, input, input_attr, labels,
                                          labels_attr, None)

            # TODO: simplify
            rhs_eq = labels_attr["equations"][i]["rhs"]
            if type(rhs_eq) == LabelInt:
                rhs = labels[rhs_eq]
            else:
                rhs = rhs_eq

            wgt_eq = labels_attr["equations"][i]["weight"]
            if wgt_eq is None:
                wgt = None
            elif type(wgt_eq) == LabelInt:
                wgt = labels[wgt_eq]
            elif np.isscalar(wgt_eq):
                wgt = wgt_eq
            else:
                pass
                # TODO: error out

            if rhs is None:
                if wgt is None:
                    loss += paddle.norm(rst**2, p=1)
                else:
                    loss += paddle.norm(rst**2 * wgt, p=1)
            else:
                if wgt is None:
                    loss += paddle.norm((rst - rhs)**2, p=1)
                else:
                    loss += paddle.norm((rst - rhs)**2 * wgt, p=1)

        return loss, cmploss.outs

    # compute loss on one boundary
    # there are multiple bc on one boundary
    def bc_loss(self, pde, net, name_b, input, input_attr, labels, labels_attr,
                bs):

        cmploss = CompFormula(pde, net)

        # compute outs, jacobian, hessian
        cmploss.compute_outs_der(input, bs)  # TODO: dirichlet not need der

        loss = 0.0
        for i in range(len(pde.bc[name_b])):
            # TODO: hard code bs
            formula = pde.bc[name_b][i].formula
            rst = cmploss.compute_formula(formula, input, input_attr, labels,
                                          labels_attr, None)

            # TODO: simplify                                  
            rhs_b = labels_attr["bc"][name_b][i]["rhs"]
            if type(rhs_b) == LabelInt:
                rhs = labels[rhs_b]
            else:
                rhs = rhs_b

            wgt_b = labels_attr["bc"][name_b][i]["weight"]
            if wgt_b is None:
                wgt = None
            elif type(wgt_b) == LabelInt:
                wgt = labels[wgt_b]
            else:
                wgt = wgt_b

            if rhs is None:
                if wgt is None:
                    loss += paddle.norm(rst**2, p=1)
                else:
                    loss += paddle.norm(rst**2 * wgt, p=1)
            else:
                if wgt is None:
                    loss += paddle.norm((rst - rhs)**2, p=1)
                else:
                    loss += paddle.norm((rst - rhs)**2 * wgt, p=1)

            # print("rhs: ", rhs)
            # exit()

        return loss, cmploss.outs

    def ic_loss(self, pde, net, input, input_attr, labels, labels_attr, bs):

        # compute outs
        cmploss = CompFormula(pde, net)
        cmploss.compute_outs(input, bs)

        loss = 0.0
        for i in range(len(pde.ic)):
            formula = pde.ic[i].formula
            rst = cmploss.compute_formula(formula, input, input_attr, labels,
                                          labels_attr, None)

            rhs_c = labels_attr["ic"][i]["rhs"]
            if type(rhs_c) == LabelInt:
                rhs = labels[rhs_c]
            else:
                rhs = rhs_c
            wgt = labels_attr["ic"][i]["weight"]
            loss += paddle.norm((rst - rhs)**2 * wgt, p=1)

        return loss, cmploss.outs

    # compute loss on real data 
    def data_loss(self, pde, net, input, input_attr, labels, labels_attr, bs):

        cmploss = CompFormula(pde, net)

        # compute outs
        cmploss.compute_outs(input, bs)

        loss = 0.0
        for i in range(len(pde.dvar)):
            idx = labels_attr["data_next"][i]
            data = labels[idx]
            loss += paddle.norm(cmploss.outs[:, i] - data, p=2)**2
            # TODO: p=2 p=1

        loss = self.data_weight * loss
        return loss, cmploss.outs