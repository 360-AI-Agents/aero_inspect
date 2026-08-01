# Dataset Research

## Overview

As part of the initial project phase, we started exploring publicly available datasets for PPE Detection and Construction Component Detection.

The goal is to identify datasets that are suitable for training and evaluating YOLOv8 models for our MVP while ensuring good annotation quality and real-world relevance.

---

## PPE Detection

### What is PPE?

PPE stands for **Personal Protective Equipment**.

In construction sites, workers are expected to wear safety equipment such as:

* Safety Helmets
* Safety Vests
* Safety Boots
* Safety Gloves
* Safety Goggles

For the MVP, we are focusing on:

* Helmet Detection
* Safety Vest Detection

### Why PPE Detection?

PPE violations are one of the most common safety concerns on construction sites.

The objective is to automatically identify whether workers are wearing the required safety equipment and generate compliance insights that can help safety officers monitor sites more efficiently.

### Potential Datasets

* Construction Site Safety Dataset
* Roboflow PPE Dataset
* Hard Hat Workers Dataset

### Current Status

* Researching publicly available datasets
* Comparing dataset quality and annotation standards
* Evaluating suitability for YOLOv8 training
* Shortlisting datasets for MVP implementation

---

## Construction Component Detection

### Objective

Identify construction site elements such as:

* Scaffolding
* Columns
* Beams
* Concrete Structures

### Why Construction Component Detection?

Beyond safety monitoring, identifying construction components can help:

* Track construction progress
* Generate site analytics
* Improve project visibility
* Support automated inspection workflows

### Current Status

* Exploring available datasets and labels
* Identifying components that are useful for progress tracking
* Evaluating data availability for MVP implementation

---

## Next Steps

* Finalize PPE Detection datasets
* Finalize Construction Component Detection datasets
* Prepare dataset preprocessing pipeline
* Set up YOLOv8 development environment
* Begin initial model experimentation
* Evaluate model performance and feasibility for MVP deployment
