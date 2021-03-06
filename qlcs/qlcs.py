#!/usr/bin/env python
# -*- coding: utf-8

"""
Search longest common substrings using generalized suffix trees built with Ukkonen's algorithm

Author: Ilya Stepanov <code at ilyastepanov.com>

(c) 2013

Adapted by Luca Mondada to output all substring matches
"""


import sys
import re
import argparse
from itertools import repeat

# some crazy value = infinity
END_OF_STRING = 10**10


class SuffixTreeNode:
    """
    Suffix tree node class. Actually, it also respresents a tree edge that points to this node.
    """
    new_identifier = 0

    def __init__(self, start=0, end=END_OF_STRING):
        self.identifier = SuffixTreeNode.new_identifier
        SuffixTreeNode.new_identifier += 1

        # suffix link is required by Ukkonen's algorithm
        self.suffix_link = None

        # child edges/nodes, each dict key represents the first letter of an edge
        self.edges = {}

        # stores reference to parent
        self.parent = None

        # bit vector shows to which strings this node belongs
        self.bit_vector = 0

        # edge info: start index and end index
        self.start = start
        self.end = end

    def add_child(self, key, start, end):
        """
        Create a new child node

        Agrs:
            key: a char that will be used during active edge searching
            start, end: node's edge start and end indices

        Returns:
            created child node

        """
        child = SuffixTreeNode(start=start, end=end)
        child.parent = self
        self.edges[key] = child
        return child

    def add_exisiting_node_as_child(self, key, node):
        """
        Add an existing node as a child

        Args:
            key: a char that will be used during active edge searching
            node: a node that will be added as a child
        """
        node.parent = self
        self.edges[key] = node

    def get_edge_length(self, current_index):
        """
        Get length of an edge that points to this node

        Args:
            current_index: index of current processing symbol (usefull for leaf nodes that have "infinity" end index)
        """
        return min(self.end, current_index + 1) - self.start

    def __str__(self):
        return 'id=' + str(self.identifier)


class SuffixTree:
    """
    Generalized suffix tree
    """

    def __init__(self):
        # the root node
        self.root = SuffixTreeNode()

        # all strings are concatenaited together. Tree's nodes store only indices
        self.input_string = ''

        # number of strings stored by this tree
        self.strings_count = 0

        # list of tree leaves
        self.leaves = []
        
        # each string belongs to a class
        # we will find substrings that appear in each class at least once
        self.classes = {}

    def append_string(self, input_string, class_id = None):
        """
        Add new string to the suffix tree
        """
        start_index = len(self.input_string)
        current_string_index = self.strings_count

        # each sting should have a unique ending
        input_string += '$' + str(current_string_index)

        # gathering 'em all together
        self.input_string += input_string
        self.strings_count += 1
        
        # assigning string to a class
        if class_id is None:
            class_id = '$' + str(current_string_index)
        try:
            self.classes[class_id].append(current_string_index)
        except KeyError:
            self.classes[class_id] = [current_string_index]

        # these 3 variables represents current "active point"
        active_node = self.root
        active_edge = 0
        active_length = 0

        # shows how many
        remainder = 0

        # new leaves appended to tree
        new_leaves = []

        # main circle
        for index in range(start_index, len(self.input_string)):
            previous_node = None
            remainder += 1
            while remainder > 0:
                if active_length == 0:
                    active_edge = index

                if self.input_string[active_edge] not in active_node.edges:
                    # no edge starting with current char, so creating a new leaf node
                    leaf_node = active_node.add_child(self.input_string[active_edge], index, END_OF_STRING)

                    # a leaf node will always be leaf node belonging to only one string
                    # (because each string has different termination)
                    leaf_node.bit_vector = 1 << current_string_index
                    new_leaves.append(leaf_node)

                    # doing suffix link magic
                    if previous_node is not None:
                        previous_node.suffix_link = active_node
                    previous_node = active_node
                else:
                    # ok, we've got an active edge
                    next_node = active_node.edges[self.input_string[active_edge]]

                    # walking down through edges (if active_length is bigger than edge length)
                    next_edge_length = next_node.get_edge_length(index)
                    if active_length >= next_node.get_edge_length(index):
                        active_edge += next_edge_length
                        active_length -= next_edge_length
                        active_node = next_node
                        continue

                    # current edge already contains the suffix we need to insert.
                    # Increase the active_length and go forward
                    if self.input_string[next_node.start + active_length] == self.input_string[index]:
                        active_length += 1
                        if previous_node is not None:
                            previous_node.suffix_link = active_node
                        previous_node = active_node
                        break

                    # splitting edge
                    split_node = active_node.add_child(
                        self.input_string[active_edge],
                        next_node.start,
                        next_node.start + active_length
                    )
                    next_node.start += active_length
                    split_node.add_exisiting_node_as_child(self.input_string[next_node.start], next_node)
                    leaf_node = split_node.add_child(self.input_string[index], index, END_OF_STRING)
                    leaf_node.bit_vector = 1 << current_string_index
                    new_leaves.append(leaf_node)

                    # suffix link magic again
                    if previous_node is not None:
                        previous_node.suffix_link = split_node
                    previous_node = split_node

                remainder -= 1

                # follow suffix link (if exists) or go to root
                if active_node == self.root and active_length > 0:
                    active_length -= 1
                    active_edge = index - remainder + 1
                else:
                    active_node = active_node.suffix_link if active_node.suffix_link is not None else self.root

        # update leaves ends from "infinity" to actual string end
        for leaf in new_leaves:
            leaf.end = len(self.input_string)
        self.leaves.extend(new_leaves)

    def find_common_substrings(self, min_substr_len=2):
        """
        Search longest common substrings in the tree by locating lowest common ancestors what belong to all strings
        """
        
        lowest_common_ancestors = set()

        # going up to the root
        for leaf in self.leaves:
            node = leaf
            prev_bit_vector = 0
            while node is not None:
                if prev_bit_vector != 0 and (node.bit_vector | prev_bit_vector) == node.bit_vector:
                    # no point in propagating further - we've been here before
                    break
                # propagating bit vector
                node.bit_vector |= prev_bit_vector
                
                if self.is_successful(node.bit_vector):
                    # hey, we've found a lowest common ancestor!
                    lowest_common_ancestors.add(node)
                prev_bit_vector = node.bit_vector
                node = node.parent

        common_substrings_set = set()
        return_value = {}
        
        longest_length = 0

        # need to filter the result array and get the longest common strings
        for common_ancestor in lowest_common_ancestors:
            common_substring = ''
            node = common_ancestor
            while node.parent is not None:
                label = self.input_string[node.start:node.end]
                common_substring = label + common_substring
                node = node.parent
            # remove unique endings ($<number>), we don't need them anymore
            common_substring = re.sub(r'(.*?)\$?\d*$', r'\1', common_substring)
            if len(common_substring) >= min_substr_len:
                if common_substring not in common_substrings_set:
                    positions = self.find_leaves_in_subtree(common_ancestor)
                    positions = self._format_positions(
                            positions,
                            common_ancestor.end-common_ancestor.start,
                            len(common_substring),
                            self.get_string_lengths()
                    )
                    
                    common_substrings_set.add(common_substring)
                    return_value[common_substring] = positions
          
        return return_value
            
    def to_graphviz(self, node=None, output=''):
        """
        Show the tree as graphviz string. For debugging purposes only
        """
        if node is None:
            node = self.root
            output = 'digraph G {edge [arrowsize=0.4,fontsize=10];'

        output +=\
            str(node.identifier) + '[label="' +\
            str(node.identifier) + '\\n' + '{0:b}'.format(node.bit_vector).zfill(self.strings_count) + '"'
        if node.bit_vector == 2 ** self.strings_count - 1:
            output += ',style="filled",fillcolor="red"'
        output += '];'
        if node.suffix_link is not None:
            output += str(node.identifier) + '->' + str(node.suffix_link.identifier) + '[style="dashed"];'

        for child in node.edges.values():
            label = self.input_string[child.start:child.end]
            output += str(node.identifier) + '->' + str(child.identifier) + '[label="' + label + '"];'
            output = self.to_graphviz(child, output)

        if node == self.root:
            output += '}'

        return output

    def is_successful(self, bit_vector):
        """
        checks whether bit_vector contains a one bit in each string class
        """
        for cls in self.classes.values():
            for representative in cls:
                if (bit_vector >> representative) % 2 == 1:
                    break
            else:
                return False
        return True
        
    def __str__(self):
        return self.to_graphviz()

    def find_leaves_in_subtree(self, root):
            """
            Finds leaves in subtree of root.
            Returns the depth of each leaf with its associated string id
            """
            
            # vals is a list of (substr identifiers, depth)
            vals = []
            
            substr_len = self.input_string[root.start:root.end].find('$')
            
            # this node contains the end of the string (ie contains $)
            if substr_len >= 0:
                vals.extend(zip(_extract_identifiers(root.bit_vector), repeat(substr_len)))
            else:
                for k,child in root.edges.items():
                    # get values for this child and increase depth by one: tple = (id, depth)
                    new_vals = self.find_leaves_in_subtree(child)
                    new_vals = map(lambda tple: (tple[0], tple[1]+root.end-root.start), new_vals)
                    
                    vals.extend(new_vals)
            return vals
    
    def get_string_lengths(self):
        """
        breaks up input_string in strings and returns their length
        """
        l = self.input_string.split('$')
        l = [s.strip('0123456789') for s in l]
        return list(map(len, l))
        
    def _format_positions(self, positions, node_substr_len, matching_len, sizes):
        """
        Changes formatting from [(id,offset_from_last)] to [id:index_from_begin]
        """
        return_value = [[] for i in range(self.strings_count)]
        for identifiers, from_last in positions:
            index = sizes[identifiers] - (from_last-node_substr_len) - matching_len
            return_value[identifiers].append(index)
        return return_value

def _extract_identifiers(bit_vector):
    """
    given a bit_vector returns an array of set bits
    """
    ids = []
    identifier = 0
    while bit_vector > 0:
        if bit_vector % 2 == 1:
            ids.append(identifier)
        bit_vector >>= 1
        identifier += 1
    return ids