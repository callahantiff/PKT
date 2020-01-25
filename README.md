## PheKnowLator

A repository for building biomedical knowledge graphs of human disease mechanisms. Detailed information regarding this project can be found on the associated [Wiki](https://github.com/callahantiff/PheKnowLater/wiki).  
<img src="https://zenodo.org/badge/DOI/10.5281/zenodo.3401437.svg"> 

**This is a Reproducible Research Repository:** This repository contains more than just code, it provides a detailed and transparent narrative of our research process. For detailed information on how we use GitHub as a reproducible research platform, click [here](https://github.com/callahantiff/Abra-Collaboratory/wiki/Using-GitHub-as-a-Reproducible-Research-Platform).

<img src="https://img.shields.io/badge/ReproducibleResearch-AbraCollaboratory-magenta.svg?style=flat-square" alt="git-AbraCollaboratory"> 

<br>  

**Project Stats:** ![GitHub contributors](https://img.shields.io/github/contributors/callahantiff/PheKnowLater.svg?color=yellow&style=flat-square) ![Github all releases](https://img.shields.io/github/downloads/callahantiff/PheKnowLater/total.svg?color=dodgerblue&style=flat-square)

***

### Releases  
All code and output for each release are free to download, see [Wiki](https://github.com/callahantiff/PheKnowLator/wiki) for full release archive.  

**Current Release:** [v2.0.0](https://github.com/callahantiff/PheKnowLator/wiki/v2.0.0). Data and code can be directly downloaded [here](https://github.com/callahantiff/PheKnowLator/wiki/v2.0.0#generated-output)

*** 

### Getting Started

**🛑 Dependencies 🛑**  
- [x] This program requires Python version 3.6. To install required modules, run the following:  
    ```
    pip install -r requirements.txt
    ``` 
- [x] Run the  **[`Data_Preparation.ipynb`](https://github.com/callahantiff/PheKnowLator/blob/master/Data_Preparation.ipynb)** notebook to build mapping, filtering, and labeling datasets. 
- [x] **Important.** This code depends on four documents in order to run successfully. See **STEP 1: Prepare Input
 Documents** below for more 
 details.
- [x] [OWLTools](https://github.com/owlcollab/owltools) library. Please download it to `resources/lib/` prior to running `main.py`. 
- [x] Knowledge graph embeddings are generated using [n1-standard1](https://cloud.google.com/compute/vm-instance-pricing#n1_predefined) Google Compute virtual machines.  

<br>

**Data Sources:** This knowledge graph is built entirely on publicly available linked open data and [Open Biomedical Ontologies](http://obofoundry.org/).
  - Please see the [Data Source](https://github.com/callahantiff/PheKnowLator/wiki/Data-Sources) Wiki page for
  information.

<br>

**Running Code:**  
This program can be run using a Jupyter Notebook ([`main.ipynb`](https://github.com/callahantiff/pheknowlator/blob/master/main.ipynb)) or from the command line ([`main.py`](https://github.com/callahantiff/pheknowlator/blob/master/main.py)) by:

``` bash
python3 Main.py -h
    
usage: Main.py [-h] -o ONTS -c CLS -i INST
    
PheKnowLator: This program builds a biomedical knowledge graph using Open Biomedical Ontologies and linked open data. The programs takes the following arguments:
    
optional arguments:
    -h, --help            show this help message and exit
    -o ONTS, --onts ONTS  name/path to text file containing ontologies
    -c CLS, --cls CLS     name/path to text file containing class sources
    -i INST, --inst INST  name/path to text file containing instance sources
```   

***

#### Workflow   
The [KG Construction](https://github.com/callahantiff/PheKnowLator/wiki/KG-Construction) Wiki page provides a detailed description of the knowledge construction process. A brief overview of this process is also provided
  provided below. 

**STEP 1: Prepare Input Documents**  
This code depends on four documents in order to run successfully. For information on what's included in these documents, see the [Document Dependencies](https://github.com/callahantiff/PheKnowLator/wiki/Dependencies) Wiki page.

For assistance in creating these documents, please run the following:
```bash
   python ./scripts/python/CreatesInputDocuments.py
```

<br>

**STEP 2: Download and Preprocess Data**  
   <br>
_PREPROCESS DATA:_  
 - <u>Create Mapping, Filtering, and Labeling Data</u>: The **[`Data_Preparation.ipynb`](https://github.com/callahantiff/PheKnowLator/blob/master/Data_Preparation.ipynb)** assists with the downloading and processing of all data needed to help build the knowledge graph.   

_DOWNLOAD DATA:_  
 - <u>Download Ontologies</u>: Downloads ontologies with or without imports from the [`ontology_source_list.txt
   `](https://github.com/callahantiff/PheKnowLator/blob/master/resources/ontology_source_list.txt) file. Metadata
    information from each ontology is saved to [`ontology_source_metadata.txt`](https://github.com/callahantiff/PheKnowLator/blob/master/resources/ontologies/ontology_source_metadata.txt) directory.
 - <u>Download Class Data</u>: Downloads data that is used to create connections between ontology concepts treated
   as classes and instance data from the [`class_source_list.txt`](https://github.com/callahantiff/PheKnowLator/blob/master/resources/class_source_list.txt) file. Metadata information from each source is saved
    to [`class_source_metadata.txt`](https://github.com/callahantiff/PheKnowLator/blob/master/resources/edge_data/class_source_metadata.txt) directory. 
 - <u>Download Instance Data</u>: Downloads data from the [`instance_source_list.txt`](https://github.com/callahantiff/PheKnowLator/blob/master/resources/instance_source_list.txt) file. Metadata information
    from each source is saved to [`instance_source_metadata.txt`](https://github.com/callahantiff/PheKnowLator/blob/master/resources/edge_data/instance_source_metadata.txt) directory.   

<br>

**STEP 3: Create Edge Lists**  
 - Create edges between classes and instances of classes.  
 - Create edges between instances of classes and instances of data.  

<br>

**STEP 4: Build Knowledge Graph**  
1. Merge ontologies used as classes.  
2. Add class-instance and instance-instance edges to merged ontologies.  
3. Remove disjointness axioms.  
4. Deductively close knowledge graph using [Elk reasoner](https://www.cs.ox.ac.uk/isg/tools/ELK/)  
5. Remove edges that are not clinically meaningful.  
6. Write edges (as triples) to local directory.  
7. Convert original edges to integers and write to local directory (required input format for generating embeddings).

<br>

**STEP 5: Generate Mechanism Embeddings**  
To create estimates of molecular mechanisms, we embed knowledge graph information extracted by [DeepWalk](https://github.com/phanein/deepwalk). Please see this [`README.md`](https://github.com/callahantiff/PheKnowLator/tree/master/resources/embeddings) for details.  

<br>

***

### Contributing

Please read [CONTRIBUTING.md](https://github.com/callahantiff/pheknowlator/blob/master/CONTRIBUTING.md) for details on 
our code of conduct, and the process for submitting pull requests to us.

***

### License

This project is licensed under Apache License 2.0 - see the [LICENSE.md](https://github.com/callahantiff/pheknowlator/blob/master/LICENSE) file for details.  


**Citing this Work:**  
```
@misc{callahan_tj_2019_3401437,
  author       = {Callahan, TJ},
  title        = {PheKnowLator},
  month        = mar,
  year         = 2019,
  doi          = {10.5281/zenodo.3401437},
  url          = {https://doi.org/10.5281/zenodo.3401437}
}
```   

***

### Contact

We'd love to hear from you! To get in touch with us, please [create an issue](https://github.com/callahantiff/PheKnowLator/issues/new/choose) or [send us an email](https://mail.google.com/mail/u/0/?view=cm&fs=1&tf=1&to=callahantiff@gmail.com) 💌