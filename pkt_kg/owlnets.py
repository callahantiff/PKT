#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import needed libraries
import glob
import networkx  # type: ignore
import os
import os.path
import pickle

from collections import Counter
from rdflib import Graph, BNode, Literal, URIRef  # type: ignore
from rdflib.namespace import RDF, RDFS, OWL  # type: ignore
from tqdm import tqdm  # type: ignore
from typing import Any, Dict, IO, List, Optional, Set, Tuple

from pkt_kg.utils import *

# set-up environment variables
obo = URIRef('http://purl.obolibrary.org/obo/')


class OwlNets(object):
    """Class removes OWL semantics from an ontology or knowledge graph using the OWL-NETS method. OWL-encoded or
    semantic edges are needed in a graph in order to enable a rich semantic representation. Many of the nodes in
    semantic edges are not clinically or biologically meaningful. This class is designed to decode all owl-encoded
    classes and return a knowledge graph that is semantically rich and clinically and biologically meaningful.

    KG CONSTRUCTION PURIFICATION: The method includes extra functionality to purify knowledge graphs according to an
    input construction approach type (i.e. 'instance- and subclass-based). The default approach is to leave the input
    graph alone and provide no purification steps. Alternatively, one can select "instance" or "subclass"
    purification. For more information see the purifies_graph_build() method.

    REMOVAL OF NON-OBO CLASSES: The method will remove all triples containing a owl:Class or owl:NamedIndividual that is
    not from the OBO namespace. If you do not want this functionality, comment line XXX.

    Additional Information: https://github.com/callahantiff/PheKnowLator/wiki/OWL-NETS-2.0

    Attributes:
        graph: An RDFLib object.
        write_location: A file path used for writing knowledge graph data.
        filename: A string containing the filename for the full knowledge graph.
        kg_construct_approach: A string containing the type of construction approach used to build the knowledge graph.
        owl_tools: A string pointing to the location of the owl tools library.

    Raises:
        TypeError: If graph is not an rdflib.graph object.
        ValueError: If graph is an empty rdflib.graph object.
        TypeError: If the file containing owl object properties is not a txt file.
        TypeError: If the file containing owl object properties is empty.
    """

    def __init__(self, graph: Graph, write_location: str, filename: str, kg_construct_approach: Optional[str] = None,
                 owl_tools: str = './pkt_kg/libs/owltools') -> None:

        self.owl_tools = owl_tools
        self.kg_construct_approach = kg_construct_approach
        self.write_location = write_location
        self.res_dir = os.path.relpath('/'.join(self.write_location.split('/')[:-1]))
        self.filename = filename
        self.nx_mdg: networkx.MultiDiGraph = networkx.MultiDiGraph()

        # VERIFY INPUT GRAPH
        if not isinstance(graph, Graph): raise TypeError('Graph must be an RDFLib Graph Object.')
        elif len(graph) == 0: raise ValueError('graph is empty.')
        else: self.graph = graph
        self.class_list: List = list(gets_ontology_classes(self.graph))

        # OWL-NETS CLEANING DICTIONARY
        self.owl_nets_dict: Dict = {'owl_nets': {'decoded_classes': {}, 'complementOf': {}, 'cardinality': {},
                                                 'negation': {}, 'misc': {}},
                                    'disjointWith': {}, 'filtered_triples': set(), 'non_obo_namespace': {},
                                    '{}_approach_purified'.format(self.kg_construct_approach): {}}

    def converts_rdflib_to_networkx_multidigraph(self) -> None:
        """Concerts an RDFLib Graph object into a Networkx MultiDiGraph object.

        Returns:
            None.
        """

        print('\nConverting RDFLib Graph to Networkx MultiDiGraph. Note, this process can take up to 60 minutes.')

        for s, p, o in tqdm(self.graph):
            self.nx_mdg.add_edge(s, o, **{'key': p})

        return None

    def removes_disjoint_with_axioms(self) -> None:
        """Removes owl:disjointWith axioms from an RDFLib Graph object.

        Returns:
            None.
        """

        print('Removing owl:disjointWith Axioms')

        disjoint_elements = [x[0] for x in self.graph.triples((None, None, OWL.disjointWith))]
        for x in tqdm(disjoint_elements):
            triples = list(self.graph.triples((x, None, None)))
            self.owl_nets_dict['disjointWith'][str(x)] = {tuple([(str(x[0]), str(x[1]), str(x[2])) for x in triples])}

            # remove axioms from graph
            for triple in triples:
                self.graph.remove(triple)

        return None

    def updates_class_instance_identifiers(self) -> None:
        """Iterates over all class instances in a knowledge graph that was constructed using the instance-based
        construction approach and converts pkt_BNodes back to the original ontology class identifier. A new edge for
        each triple, containing an instance of a class is updated with the original ontology identifier, is added to
        the graph.

        Assumptions: (1) all instances of a class identifier contain the pkt namespace
                     (2) all relations used when adding new edges to a graph are part of the OBO namespace

        Returns:
             None.
        """

        print('Re-mapping Instances of Classes to Class Identifiers')

        # get all class individuals in pheknowlator namespace
        pkts = [x[0] for x in list(self.graph.triples((None, RDF.type, OWL.NamedIndividual))) if 'pkt' in str(x[0])]
        remove_edges: Set = set()

        for node in tqdm(pkts):
            # get the node represented by the instance BNode
            cls = [x[2] for x in list(self.graph.triples((node, RDF.type, None))) if 'obo' in str(x[2])][0]
            # get triples where the bnode is the subject and object
            inst_triples = list(self.graph.triples((node, None, None))) + list(self.graph.triples((None, None, node)))
            for edge in inst_triples:
                if 'obo' in str(edge[1]):
                    if edge[0] == node: self.graph.add((cls, edge[1], edge[2]))
                    if edge[2] == node: self.graph.add((edge[0], edge[1], cls))
            remove_edges |= set(inst_triples)
        self.graph = remove_edges_from_graph(self.graph, list(remove_edges))

        return None

    def removes_edges_with_owl_semantics(self) -> Graph:
        """Creates a filtered knowledge graph, such that only nodes that are owl:Class/owl:Individual connected via a
        owl:ObjectProperty and not an owl:AnnotationProperty. For
        example:

            REMOVE - edges needed to support owl semantics (not biologically meaningful):
                subject: http://purl.obolibrary.org/obo/CLO_0037294
                predicate: owl:AnnotationProperty
                object: rdf:about="http://purl.obolibrary.org/obo/CLO_0037294"

            KEEP - biologically meaningful edges:
                subject: http://purl.obolibrary.org/obo/CHEBI_16130
                predicate: http://purl.obolibrary.org/obo/RO_0002606
                object: http://purl.obolibrary.org/obo/HP_0000832

        Returns:
            filtered_graph: An RDFLib graph that only contains clinically and biologically meaningful triples.
        """

        print('\nFiltering Triples')

        keep_predicates, filtered_triples = set(), set()
        for x in tqdm(self.graph):
            if isinstance(x[0], URIRef) and isinstance(x[1], URIRef) and isinstance(x[2], URIRef):
                s = [i for i in list(self.graph.triples((x[0], RDF.type, None)))
                     if (OWL.Class in i[2] or OWL.NamedIndividual in i[2]) and '#' not in str(x[0])]
                o = [i for i in list(self.graph.triples((x[2], RDF.type, None)))
                     if (OWL.Class in i[2] or OWL.NamedIndividual in i[2]) and '#' not in str(x[2])]
                p = [i for i in list(self.graph.triples((x[1], RDF.type, None))) if i[2] != OWL.AnnotationProperty]
                if len(s) > 0 and len(o) > 0 and len(p) > 0:
                    if OWL.ObjectProperty in p[0][2]: keep_predicates.add(x)
                    else: filtered_triples |= {(str(x[0]), str(x[1]), str(x[2]))}
                if len(s) > 0 and len(o) > 0 and len(p) == 0:
                    if RDFS.subClassOf in x[1]: keep_predicates.add(x)
                    elif RDF.type in x[1]: keep_predicates.add(x)
                    else: filtered_triples |= {(str(x[0]), str(x[1]), str(x[2]))}
            else: filtered_triples |= {(str(x[0]), str(x[1]), str(x[2]))}

        filtered_graph = adds_edges_to_graph(Graph(), list(keep_predicates))  # create a new graph from filtered edges
        self.owl_nets_dict['filtered_triples'] |= filtered_triples

        return filtered_graph

    def recurses_axioms(self, seen_nodes: List[BNode], axioms: List[Any]) -> List[BNode]:
        """Function recursively searches a list of graph nodes and tracks the nodes it has visited. Once all nodes in
        the input axioms list have been visited, a final unique list of relevant nodes is returned. This list is
        assumed to include all necessary BNodes needed to re-create an OWL:equivalentClass.

        Args:
            seen_nodes: A list which may or may not contain knowledge graph nodes.
            axioms: A list of axioms, e.g. [(rdflib.term.BNode('N3e23fe5f05ff4a7d992c548607c86277'),
                                            rdflib.term.URIRef('http://www.w3.org/2002/07/owl#Class'),
                                            rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'))]

        Returns:
            seen_nodes: A list of knowledge graph BNodes.
        """

        search_axioms: List = []
        tracked_nodes: List = []

        for axiom in axioms:
            for element in axiom:
                if isinstance(element, BNode) and element not in seen_nodes:
                    tracked_nodes.append(element)
                    search_axioms += list(self.nx_mdg.out_edges(element, keys=True))
        if len(tracked_nodes) > 0:
            seen_nodes += list(set(tracked_nodes))
            return self.recurses_axioms(seen_nodes, search_axioms)
        else:
            return seen_nodes

    def creates_edge_dictionary(self, node: URIRef) -> Tuple[Dict, Set]:
        """Creates a nested edge dictionary from an input class node by obtaining all outgoing edges and recursively
        looping over each anonymous out edge node. While creating the dictionary, if cardinality is used then a
        formatted string that contains the class node and the anonymous node naming the element that includes
        cardinality is constructed and added to a set.

        Args:
            node: An rdflib.term object.

        Returns:
            class_edge_dict: A nested dictionary. The outer dictionary keys are anonymous nodes and the inner keys
                are owl:ObjectProperty values from each out edge triple that comes out of that anonymous node. For
                example:
                    {rdflib.term.BNode('N3243b60f69ba468687aa3cbe4e66991f'): {
                        someValuesFrom': rdflib.term.URIRef('http://purl.obolibrary.org/obo/PATO_0000587'),
                        type': rdflib.term.URIRef('http://www.w3.org/2002/07/owl#Restriction'),
                        onProperty': rdflib.term.URIRef('http://purl.obolibrary.org/obo/RO_0000086')}}
            cardinality: A set of strings, where each string is formatted such that the substring that occurs before
                the ':' is the class node and the substring after the ':' is the anonymous node naming the element where
                cardinality was used.
        """

        matches: List = []
        class_edge_dict: Dict = dict()
        cardinality: Set = set()

        # get all edges that come out of class node
        out_edges = [x for axioms in list(self.nx_mdg.out_edges(node, keys=True)) for x in axioms]
        for axiom in out_edges:  # recursively loop over out_edge bnodes to find list of relevant edges to rebuild class
            if isinstance(axiom, BNode):
                for element in self.recurses_axioms([], list(self.nx_mdg.out_edges(axiom, keys=True))):
                    matches += list(self.nx_mdg.out_edges(element, keys=True))
        for match in matches:  # create dictionary of edge lists
            if 'cardinality' in str(match[2]).lower():
                cardinality |= {'{}: {}'.format(node, match[0])}
            else:
                if match[0] in class_edge_dict:
                    class_edge_dict[match[0]][match[2].split('#')[-1]] = {}
                    class_edge_dict[match[0]][match[2].split('#')[-1]] = match[1]
                else:
                    class_edge_dict[match[0]] = {}
                    class_edge_dict[match[0]][match[2].split('#')[-1]] = match[1]

        return class_edge_dict, cardinality

    def detects_constructed_class_to_ignore(self, node_info: Tuple, node: URIRef) -> bool:
        """Method takes a tuple of information about a node and searches the information for nodes that contain
        semantic support information, but also contains other types of information (i.e. cardinality, complementOf,
        or negation (i.e. lacks_part)) we either don't full process or want to ignore.

        Args:
            node: An RDFLib URIRef object containing node information.
            node_info: A tuple where the first item is a nested dictionary. The outer dictionary keys are anonymous
                nodes and the inner keys are owl:ObjectProperty values from each out edge triple that comes out of that
                anonymous node. The second item is a  set of strings, where each string is formatted such that the
                substring that occurs before the ':' is the class node and the substring after the ':' is the
                anonymous node naming the element where cardinality was used.

        Returns:
            True: if a class to ignore was detected.
            False: if a class to ignore was not detected.
        """

        if len(node_info[1]) != 0:  # want to note and will process ignoring the specified integer value
            self.owl_nets_dict['owl_nets']['cardinality'][str(node)] = {
                tuple([(str(x[0]), str(x[1]), str(x[2])) for x in
                       self.graph.triples((BNode(list(node_info[1])[0].split(': ')[-1]), None, None))])}
            return False
        elif any(v for v in node_info[0].values() if 'complementOf' in v.keys()):
            self.owl_nets_dict['owl_nets']['complementOf'][str(node)] = {
                tuple([(str(x[0]), str(x[1]), str(x[2])) for x in
                       self.graph.triples((list(node_info[0].keys())[0], None, None))])}
            return True
        elif any(v for v in node_info[0].items() if any(i for i in v[1].items() if 'lacks_part' in str(i))):
            self.owl_nets_dict['owl_nets']['negation'][str(node)] = {
                tuple([tuple([(str(x[0]), str(x[1]), str(x[2])) for x in self.graph.triples((k, None, None))])
                       for k, v in node_info[0].items() if 'onProperty' in v.keys()])}
            return True

        else: return False

    @staticmethod
    def returns_object_property(sub: URIRef, obj: URIRef, prop: URIRef = None) -> URIRef:
        """Checks the subject and object node types in order to determine the correct type of owl:ObjectProperty.

        The following ObjectProperties are returned for each of the following subject-object types:
            - subject + object are not PATO terms + prop is None --> rdfs:subClassOf
            - sub + obj are PATO terms + prop is None --> rdfs:subClassOf
            - sub is not a PATO term, but obj is a PATO term --> owl:RO_000086
            - sub is a PATO term + obj is a PATO term + prop is not None --> prop

        Args:
            sub: An rdflib.term object.
            obj: An rdflib.term object.
            prop: An rdflib.term object, which is provided as the value of owl:onProperty.

        Returns:
            An rdflib.term object that represents an owl:ObjectProperty.
        """

        if ('PATO' in sub and 'PATO' in obj) and not prop: return RDFS.subClassOf
        elif ('PATO' not in sub and 'PATO' not in obj) and not prop: return RDFS.subClassOf
        elif 'PATO' not in sub and 'PATO' in obj: return obo.RO_0000086
        else: return prop

    @staticmethod
    def parses_anonymous_axioms(edges: Dict, class_dict: Dict) -> Dict:
        """Parses axiom dictionaries that only include anonymous axioms (i.e. 'first' and 'rest') and returns an
        updated axiom dictionary that contains an owl:Restriction or an owl constructor (i.e. owl:unionOf or
        owl:intersectionOf).

        Args:
            edges: A subset of dictionary where keys are owl:Objects (i.e. 'first', 'rest', 'onProperty',
                or 'someValuesFrom').
            class_dict: A nested dictionary. The outer dictionary keys are anonymous nodes and the inner keys
                are owl:ObjectProperty values from each out edge triple that comes out of that anonymous node.

        Returns:
             updated_edges: A subset of dictionary where keys are owl:Objects (e.g. 'first', 'rest', 'onProperty',
                or 'someValuesFrom').
        """

        if isinstance(edges['first'], URIRef) and isinstance(edges['rest'], BNode): return class_dict[edges['rest']]
        elif isinstance(edges['first'], URIRef) and isinstance(edges['rest'], URIRef): return class_dict[edges['first']]
        elif isinstance(edges['first'], BNode) and isinstance(edges['rest'], URIRef): return class_dict[edges['first']]
        else: return {**class_dict[edges['first']], **class_dict[edges['rest']]}

    def parses_constructors(self, node: URIRef, edges: Dict, class_dict: Dict, relation: URIRef = None) \
            -> Tuple[Set, Optional[Dict]]:
        """Traverses a dictionary of rdflib objects used in the owl:unionOf or owl:intersectionOf constructors, from
        which the original set of edges used to the construct the class_node are edited, such that all owl-encoded
        information is removed. For example:
            INPUT: <!-- http://purl.obolibrary.org/obo/CL_0000995 -->
                        <owl:Class rdf:about="http://purl.obolibrary.org/obo/CL_0000995">
                            <owl:equivalentClass>
                                <owl:Class>
                                    <owl:unionOf rdf:parseType="Collection">
                                        <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0001021"/>
                                        <rdf:Description rdf:about="http://purl.obolibrary.org/obo/CL_0001026"/>
                                    </owl:unionOf>
                                </owl:Class>
                            </owl:equivalentClass>
                            <rdfs:subClassOf rdf:resource="http://purl.obolibrary.org/obo/CL_0001060"/>
                        </owl:Class>
            OUTPUT: [(CL_0000995, rdfs:subClassOf, CL_0001021), (CL_0000995, rdfs:subClassOf, CL_0001026)]

        Args:
            node: An rdflib term of type URIRef or BNode that references an OWL-encoded class.
            edges: A subset of dictionary where keys are owl:Objects (i.e. 'first', 'rest', 'onProperty',
                or 'someValuesFrom').
            class_dict: A nested dictionary. The outer dictionary keys are anonymous nodes and the inner keys
                are owl:ObjectProperty values from each out edge triple that comes out of that anonymous node.
            relation: An rdflib.URIRef object that defaults to None, but if provided by a user contains an
                owl:onProperty relation.

        Returns:
            cleaned_classes: A list of tuples, where each tuple represents a class that had OWL semantics removed.
            edge_batch: A dictionary subset, where keys are owl:Objects (e.g. 'first', 'rest', 'onProperty').
        """

        cleaned_classes: Set = set()
        edge_batch = class_dict[edges['unionOf' if 'unionOf' in edges.keys() else 'intersectionOf']]

        while edge_batch:
            if ('first' in edge_batch.keys() and 'rest' in edge_batch.keys()) and 'type' not in edge_batch.keys():
                if isinstance(edge_batch['first'], URIRef) and isinstance(edge_batch['rest'], BNode):
                    obj_property = self.returns_object_property(node, edge_batch['first'], relation)
                    cleaned_classes |= {(node, obj_property, edge_batch['first'])}
                    edge_batch = class_dict[edge_batch['rest']]
                elif isinstance(edge_batch['first'], URIRef) and isinstance(edge_batch['rest'], URIRef):
                    obj_property = self.returns_object_property(node, edge_batch['first'], relation)
                    cleaned_classes |= {(node, obj_property, edge_batch['first'])}
                    edge_batch = None
                else: edge_batch = self.parses_anonymous_axioms(edge_batch, class_dict)
            else: break

        return cleaned_classes, edge_batch

    def parses_restrictions(self, node: URIRef, edges: Dict, class_dict: Dict) -> Tuple[Set, Optional[Dict]]:
        """Parses a subset of a dictionary containing rdflib objects participating in a restriction and reconstructs the
        class (referenced by node) in order to remove owl-encoded information. An example is shown below:
            INPUT:    <!-- http://purl.obolibrary.org/obo/GO_0000785 -->
                        <owl:Class rdf:about="http://purl.obolibrary.org/obo/GO_0000785">
                            <rdfs:subClassOf rdf:resource="http://purl.obolibrary.org/obo/GO_0110165"/>
                            <rdfs:subClassOf>
                                <owl:Restriction>
                                    <owl:onProperty rdf:resource="http://purl.obolibrary.org/obo/BFO_0000050"/>
                                    <owl:someValuesFrom rdf:resource="http://purl.obolibrary.org/obo/GO_0005694"/>
                                </owl:Restriction>
                            </rdfs:subClassOf>
                        </owl:Class>
            OUTPUT: [(GO_0000785, BFO_0000050, GO_0005694)]

        Args:
            node: An rdflib term of type URIRef or BNode that references an OWL-encoded class.
            edges: A subset of dictionary where keys are owl:Objects (e.g. 'first', 'rest', 'onProperty',
                'onClass', or 'someValuesFrom').
            class_dict: A nested dictionary. The outer dictionary keys are anonymous nodes and the inner keys
                are owl:ObjectProperty values from each out edge triple that comes out of that anonymous node.

        Returns:
             cleaned_classes: A list of tuples, where each tuple represents a class with OWL semantics removed.
             edge_batch: A subset of dictionary where keys are owl:Objects (e.g. 'first', 'rest', 'onProperty',
                'onClass', or 'someValuesFrom', 'allValuesFrom).
        """

        prop_types = ['allValuesFrom', 'someValuesFrom', 'hasSelf', 'hasValue', 'onClass']
        restriction_components = ['type', 'first', 'rest', 'onProperty']
        object_type = [x for x in edges.keys() if x not in restriction_components and x in prop_types][0]
        edge_batch = edges
        cleaned_classes: Set = set()

        if isinstance(edge_batch[object_type], URIRef) or isinstance(edge_batch[object_type], Literal):
            object_node = node if object_type == 'hasSelf' else edge_batch[object_type]
            if len(edge_batch) == 3:
                cleaned_classes |= {(node, edge_batch['onProperty'], object_node)}
                return cleaned_classes, None
            else:
                cleaned_classes |= {(node, edge_batch['onProperty'], object_node)}
                return cleaned_classes, self.parses_anonymous_axioms(edge_batch, class_dict)
        else:
            axioms = class_dict[edge_batch[object_type]]
            if 'unionOf' in axioms.keys() or 'intersectionOf' in axioms.keys():
                results = self.parses_constructors(node, axioms, class_dict, edge_batch['onProperty'])
                cleaned_classes |= results[0]
                return cleaned_classes, results[1]
            else:
                return cleaned_classes, axioms

    def cleans_owl_encoded_classes(self) -> Graph:
        """Loops over a all owl:Class objects in a graph searching for edges that include owl:equivalentClass
        nodes (i.e. to find classes assembled using owl constructors) and rdfs:subClassof nodes (i.e. to find
        owl:restrictions). Once these edges are found, the method loops over the in and out edges of all anonymous nodes
        in the edges in order to decode the owl-encoded nodes.

        Returns:
             An rdflib.Graph object that has been updated to only include triples owl decoded triples.
        """

        print('\nDecoding OWL Constructors and Restrictions')

        decoded_graph: Graph = Graph()
        cleaned_nodes: Set = set()
        pbar = tqdm(total=len(self.class_list))

        while self.class_list:
            pbar.update(1)
            node = self.class_list.pop(0)
            node_info = self.creates_edge_dictionary(node)
            if len(node_info[0]) == 0: pass
            elif self.detects_constructed_class_to_ignore(node_info, node) is False: pass
            else:
                cleaned_nodes |= {node}
                cleaned_classes: Set = set()
                semantic_chunk = [x[1] for x in list(self.nx_mdg.out_edges(node, keys=True)) if isinstance(x[1], BNode)]
                for element in semantic_chunk:  # decode owl-encoded edges
                    edges = node_info[0][element]
                    while edges:
                        if 'unionOf' in edges.keys():
                            results = self.parses_constructors(node, edges, node_info[0])
                            cleaned_classes |= results[0]
                            edges = results[1]
                        elif 'intersectionOf' in edges.keys():
                            results = self.parses_constructors(node, edges, node_info[0])
                            cleaned_classes |= results[0]
                            edges = results[1]
                        elif 'Restriction' in edges['type']:
                            results = self.parses_restrictions(node, edges, node_info[0])
                            cleaned_classes |= results[0]
                            edges = results[1]
                        else:  # catch all other axioms -- only catching owl:onProperty
                            misc_axioms = [x for x in edges.keys() if x not in ['type', 'first', 'rest', 'onProperty']]
                            self.owl_nets_dict['owl_nets']['misc'][str(node)] = {tuple(misc_axioms)}
                            edges = None
                # add kept edges to filtered graph
                decoded_graph = adds_edges_to_graph(decoded_graph, list(cleaned_classes))
                self.owl_nets_dict['owl_nets']['decoded_classes'][str(node)] = {
                    tuple([(str(x[0]), str(x[1]), str(x[2])) for x in cleaned_classes])}
        pbar.close()
        # del self.nx_mdg  # delete networkx graph object to free up memory
        print('=' * 75 + '\nDecoded {} owl-encoded classes. Note the following:'.format(len(cleaned_nodes)))
        print('{} cardinality elements'.format(len(list(self.owl_nets_dict['owl_nets']['cardinality'].keys()))))
        print('ignored {} misc elements'.format(len(list(self.owl_nets_dict['owl_nets']['misc'].keys()))))
        print('{} owl:complementOf removed'.format(len(list(self.owl_nets_dict['owl_nets']['complementOf'].keys()))))
        print('=' * 75 + '\n{} negation elements'.format(len(list(self.owl_nets_dict['owl_nets']['negation'].keys()))))

        return decoded_graph

    def removes_non_obo_namespace_triples(self) -> None:
        """

        Returns:
             None.
        """

        y = set(['/'.join(str(x[0]).split('/')[:-1]) for x in keep_predicates if 'obo' not in str(x[0])])
        y_list = list(y)
        for x in keep_predicates:
            s = [i for i in list(self.graph.triples((x[0], RDF.type, None)))
                 if (OWL.Class in i[2] or OWL.NamedIndividual in i[2]) and '#' not in str(x[0])][0][2].split('#')[-1]
            o = [i for i in list(graph.triples((x[2], RDF.type, None)))
                 if (OWL.Class in i[2] or OWL.NamedIndividual in i[2]) and '#' not in str(x[2])][0][2].split('#')[-1]
            if str(x[0]).startswith(y_list[0]) or str(x[0]).startswith(y_list[2]):
                print(str(x[0]), str(s), str(x[1]).split('#')[-1], str(x[2]), str(o))

        # make final sweep over graph and remove any triples with a sub/obj containing an owl class object
        print('\nVerifying OWL-NETS Nodes')
        for x in tqdm(owl_nets_graph):
            if 'owl#' in str(x[0]) or 'owl#' in str(x[2]): owl_nets_graph.remove(x)

        self.owl_nets_dict['non_obo_namespace'][str(node)] = {tuple()}

        return None

    def purifies_graph_build(self) -> None:
        """

        Returns:
             None
        """

        if self.kg_construct_approach is None:
            return None
        else:
            

        gets_class_ancestors(self.graph, class_uris)

        return None

    def run_owl_nets(self) -> Graph:
        """Performs all steps of the OWL-NETS pipeline, including: (1) removes owl:disjointWith axioms; (2) mapping all
        instances of class identifiers back to original class identifiers; (3) filters a graph to remove all triples
        that contain only semantic support triples; (4) decodes all owl-encoded classes of type intersection and union
        constructor and all restrictions; (5) removes non-OBO namespace classes; and (6) purifies decoded graph to
        input construction approach (i.e. None, subclass-based or instance-based).

        NOTE. It is important to check the number of unique nodes and relations in OWL-NETS and to compare the counts
        with and without the URIs (i.e. http://purl.obolibrary.org/obo/HP_0000000 vs HP_0000000). Doing this provides a
        nice sanity check and can help identify duplicate nodes (i.e. nodes with the same identifier, but different
        URIs -- where the URIs should be the same).

        Returns:
            An rdflib.Graph object that has been updated to only include triples owl decoded triples.
        """

        print('\nCreating OWL-NETS graph')

        self.removes_disjoint_with_axioms()
        self.test_converts_rdflib_to_networkx_multidigraph()  # create networkx representation
        if self.kg_construct_approach == 'instance': self.updates_class_instance_identifiers()
        filtered_graph = self.removes_edges_with_owl_semantics()  # filter out owl-encoded triples from original KG
        self.graph = self.cleans_owl_encoded_classes()  # decode owl constructors and restrictions
        owl_nets_graph = filtered_graph + self.removes_edges_with_owl_semantics()  # prune bad triples from decoded
        self.removes_non_obo_namespace_triples()  # removes non-obo namespace nodes
        self.purifies_graph_build()  # purifies decoded graph to input kg construction approach

        # write out owl-nets graph
        print('\nSerializing OWL-NETS Graph')
        file_name = self.filename[:-4] + '_OWLNETS.nt'
        owl_nets_graph.serialize(destination=self.write_location + file_name, format='nt')

        # get output statistics
        unique_nodes = set([str(x) for y in [node[0::2] for node in list(owl_nets_graph)] for x in y])
        unique_relations = set([str(rel[1]) for rel in list(owl_nets_graph)])
        gets_ontology_statistics(self.write_location + file_name, self.owl_tools)
        print('The OWL-Decoded Knowledge Graph Contains: {} Triples'.format(len(owl_nets_graph)))
        print('The OWL-Decoded Knowledge Graph Contains: {} Unique Nodes'.format(len(unique_nodes)))
        print('The OWL-Decoded Knowledge Graph Contains: {} Unique Relations'.format(len(unique_relations)))

        # write out owl_nets dictionary
        with open(self.write_location + 'OWL-NETS_semantic_decoding_dict.pkl', 'wb') as out:
            pickle.dump(self.owl_nets_dict, out)

        # convert graph to NetworkX MultiDigraph
        converts_rdflib_to_networkx(self.write_location, file_name[:-3], owl_nets_graph)

        return owl_nets_graph
