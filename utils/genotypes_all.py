""" Genotypes
    - Genotype: normal/reduce gene + normal/reduce cell output connection (concat)
    - gene: discrete ops information (w/o output connection)
    - dag: real ops (can be mixed or discrete, but Genotype has only discrete information itself)
"""
from collections import namedtuple
import torch
import torch.nn as nn
#from models import darts_ops as ops


Genotype = namedtuple('Genotype', 'normal normal_concat reduce reduce_concat')

field_name = ''
n_layers = 6
for i in range(n_layers):
    field_name += chr(i + 97) + ' ' + chr(i + 97) + '_concat'
    if i < n_layers - 1:
        field_name += ' '
Genotype_6 = namedtuple('Genotype', field_name)

PRIMITIVES = [
    'max_pool_3x3',
    'avg_pool_3x3',
    'skip_connect', # identity
    'sep_conv_3x3',
    'sep_conv_5x5',
    'sep_conv_m_3x3',
    'sep_conv_m_5x5',
    'conv_3x3',
    'conv_5x5',
    'conv_3x3',#5
    'conv_5x5',#6
    'gab_filt_3x3',
    'dtp_blok_3x3',
    # 'gas_blok_3x3',
    # 'none'
]


def to_dag(C_in, gene, reduction):
    """ generate discrete ops from gene """
    dag = nn.ModuleList()
    for edges in gene:
        row = nn.ModuleList()
        for op_name, s_idx in edges:
            # reduction cell & from input nodes => stride = 2
            stride = 2 if reduction and s_idx < 2 else 1
            op = ops.OPS[op_name](C_in, stride, True)
            if not isinstance(op, ops.Identity): # Identity does not use drop path
                op = nn.Sequential(
                    op,
                    ops.DropPath_()
                )
            op.s_idx = s_idx
            row.append(op)
        dag.append(row)

    return dag


def from_str(s):
    """ generate genotype from string
    e.g. "Genotype(
            normal=[[('sep_conv_3x3', 0), ('sep_conv_3x3', 1)],
                    [('sep_conv_3x3', 1), ('conv_3x3', 2)],
                    [('sep_conv_3x3', 1), ('sep_conv_3x3', 2)],
                    [('sep_conv_3x3', 1), ('conv_3x3', 4)]],
            normal_concat=range(2, 6),
            reduce=[[('max_pool_3x3', 0), ('max_pool_3x3', 1)],
                    [('max_pool_3x3', 0), ('skip_connect', 2)],
                    [('max_pool_3x3', 0), ('skip_connect', 2)],
                    [('max_pool_3x3', 0), ('skip_connect', 2)]],
            reduce_concat=range(2, 6))"
    """

    genotype = eval(s)

    return genotype


def parse(alpha, k):
    """
    parse continuous alpha to discrete gene.
    alpha is ParameterList:
    ParameterList [
        Parameter(n_edges1, n_ops),
        Parameter(n_edges2, n_ops),
        ...
    ]

    gene is list:
    [
        [('node1_ops_1', node_idx), ..., ('node1_ops_k', node_idx)],
        [('node2_ops_1', node_idx), ..., ('node2_ops_k', node_idx)],
        ...
    ]
    each node has two edges (k=2) in CNN.
    """

    gene = []
    # assert PRIMITIVES[-1] == 'none' # assume last PRIMITIVE is 'none'

    # 1) Convert the mixed op to discrete edge (single op) by choosing top-1 weight edge
    # 2) Choose top-k edges per node by edge score (top-1 weight in edge)
    for edges in alpha:
        # edges: Tensor(n_edges, n_ops)
        edge_max, primitive_indices = torch.topk(edges, 1)
        # edge_max, primitive_indices = torch.topk(edges[:, :-1], 1) # ignore 'none'
        topk_edge_values, topk_edge_indices = torch.topk(edge_max.view(-1), k)
        node_gene = []
        for edge_idx in topk_edge_indices:
            prim_idx = primitive_indices[edge_idx]
            prim = PRIMITIVES[prim_idx]
            node_gene.append((prim, edge_idx.item()))

        gene.append(node_gene)

    return gene


def parse_numpy(alpha, k):
    """
    parse continuous alpha to discrete gene.
    alpha is ParameterList:
    ParameterList [
        Parameter(n_edges1, n_ops),
        Parameter(n_edges2, n_ops),
        ...
    ]

    gene is list:
    [
        [('node1_ops_1', node_idx), ..., ('node1_ops_k', node_idx)],
        [('node2_ops_1', node_idx), ..., ('node2_ops_k', node_idx)],
        ...
    ]
    each node has two edges (k=2) in CNN.
    """

    gene = []
    # assert PRIMITIVES[-1] == 'none' # assume last PRIMITIVE is 'none'

    # 1) Convert the mixed op to discrete edge (single op) by choosing top-1 weight edge
    # 2) Choose top-k edges per node by edge score (top-1 weight in edge)
    for edges in alpha:
        # edges: Tensor(n_edges, n_ops)
        edge_max, primitive_indices = torch.topk(torch.tensor(edges), 1)
        # edge_max, primitive_indices = torch.topk(torch.tensor(edges[:, :-1]), 1) # ignore 'none'
        # edge_max, primitive_indices = torch.topk(edges[:, :-1].clone().detach(), 1) # ignore 'none'
        topk_edge_values, topk_edge_indices = torch.topk(edge_max.view(-1), k)
        node_gene = []
        for edge_idx in topk_edge_indices:
            prim_idx = primitive_indices[edge_idx]
            prim = PRIMITIVES[prim_idx]
            node_gene.append((prim, edge_idx.item()))

        gene.append(node_gene)

    return gene


ABANDIT_CIFAR_1 = Genotype_6(
    a=[[('conv_3x3', 0)], [('gab_filt_3x3', 1)], [('sep_conv_3x3', 2)], [('dtp_blok_3x3', 1)]], a_concat=range(1, 5),
    b=[[('avg_pool_3x3', 0)], [('gab_filt_3x3', 0)], [('sep_conv_5x5', 2)], [('conv_3x3', 1)]], b_concat=range(1, 5),
    c=[[('conv_3x3', 0)], [('max_pool_3x3', 0)], [('conv_5x5', 0)], [('sep_conv_5x5', 3)]], c_concat=range(1, 5),
    d=[[('dtp_blok_3x3', 0)], [('sep_conv_5x5', 1)], [('avg_pool_3x3', 2)], [('conv_3x3', 3)]], d_concat=range(1, 5),
    e=[[('dtp_blok_3x3', 0)], [('sep_conv_5x5', 1)], [('sep_conv_3x3', 1)], [('avg_pool_3x3', 3)]], e_concat=range(1, 5),
    f=[[('gab_filt_3x3', 0)], [('conv_3x3', 0)], [('dtp_blok_3x3', 1)], [('avg_pool_3x3', 2)]], f_concat=range(1, 5))

ABANDIT_CIFAR_2 = Genotype_6(a=[[('dtp_blok_3x3', 0)], [('sep_conv_3x3', 0)], [('conv_3x3', 1)], [('sep_conv_3x3', 3)]], a_concat=range(1, 5), 
    b=[[('conv_5x5', 0)], [('gab_filt_3x3', 0)], [('max_pool_3x3', 0)], [('dtp_blok_3x3', 2)]], b_concat=range(1, 5), 
    c=[[('sep_conv_3x3', 0)], [('dtp_blok_3x3', 0)], [('max_pool_3x3', 1)], [('sep_conv_5x5', 3)]], c_concat=range(1, 5), 
    d=[[('sep_conv_5x5', 0)], [('dtp_blok_3x3', 0)], [('gab_filt_3x3', 2)], [('conv_3x3', 1)]], d_concat=range(1, 5), 
    e=[[('sep_conv_5x5', 0)], [('skip_connect', 1)], [('sep_conv_5x5', 1)], [('sep_conv_5x5', 1)]], e_concat=range(1, 5), 
    f=[[('max_pool_3x3', 0)], [('skip_connect', 0)], [('sep_conv_5x5', 2)], [('gab_filt_3x3', 0)]], f_concat=range(1, 5))
genotype_array = {
    'ABANDIT_CIFAR_1': ABANDIT_CIFAR_1,
    'ABANDIT_CIFAR_2': ABANDIT_CIFAR_2,
    }
