# EML Fractal Explorer
Original paper on eml(x,y) operator here: https://arxiv.org/html/2603.21852v2

Original paper on eml(x,y) operator here: https://arxiv.org/html/2603.21852v2

Original paper on eml(x,y) operator here: https://arxiv.org/html/2603.21852v2

## Overview

This project explores a novel Mandelbrot-like fractal defined using the operator eml(x,y) described by Andrzej Odrzywołek in: https://arxiv.org/html/2603.21852v2

[
elm(a, b) = e^a - \ln(b)
]

Instead of the classical quadratic iteration, we define a complex dynamical system based on:

[
z_{n+1} = e^{z_n} - \Log(c), \quad z_0 = 0
]

where:

* (c \in \mathbb{C}) is the parameter (pixel coordinate),
* (\Log) is the principal branch of the complex logarithm.

The goal is to study and visualize the set of complex numbers (c) for which the orbit of (z_0 = 0) remains bounded.

---

## Goals

1. Build an interactive visualization tool for the EML Fractal set.
2. Explore the structure and properties of this fractal.
3. Experiment with alternative parameterizations and iteration rules.
4. Optimize rendering performance for real-time exploration.
5. Investigate mathematical properties (stability regions, periodic orbits, etc.).

---

## Core Definition

Primary iteration:

```
z_0 = 0
z_{n+1} = exp(z_n) - Log(c)
```

Escape condition:

```
|z_n| > R  → orbit escapes
```

Typical parameters:

* `R = 20`
* `max_iter = 50–200`

---

## Alternative Formulation (Recommended)

To avoid branch issues with `Log(c)`, use:

```
z_{n+1} = exp(z_n) + λ
```

where:

```
λ = -Log(c)
```

This is numerically more stable and easier to explore.

---

## Current Features

* Static rendering of EML Fractal set
* Interactive navigation:

  * Mouse scroll → zoom
  * Left-click + drag → pan
* Escape-time coloring

---

## Next Development Tasks (Claude Code)

### 1. Performance Optimization

* Replace nested Python loops with NumPy vectorization
* Explore Numba / Cython acceleration
* Optional GPU (CuPy / PyTorch)

### 2. Rendering Improvements

* Smooth coloring refinements
* Histogram coloring
* Continuous potential coloring
* Anti-aliasing

### 3. UI Enhancements

* Add zoom rectangle (right-click drag)
* Reset view button
* Iteration depth slider
* Real-time parameter controls

### 4. Alternative Dynamics

Implement and compare:

* `z_{n+1} = exp(z_n) + λ`
* `z_{n+1} = elm(z_n, c)`
* Hybrid systems:

  ```
  z_{n+1} = exp(z_n) - α·Log(c)
  ```
* Multi-branch logarithm exploration

### 5. Julia Sets

For fixed parameter:

```
f_c(z) = exp(z) - Log(c)
```

Render corresponding Julia sets.

### 6. Numerical Stability

* Handle overflow in `exp(z)`
* Clamp / rescale large values
* Explore log-domain computations

### 7. Mathematical Exploration

* Detect periodic cycles
* Identify stability regions
* Compare with classical Mandelbrot
* Study effect of complex logarithm branches

---

## Architecture Suggestions

### Core Modules

* `compute.py`

  * iteration functions
  * escape-time computation

* `render.py`

  * image generation
  * coloring algorithms

* `viewer.py`

  * interactive UI (matplotlib / PyQt / web)

* `experiments/`

  * alternative formulas
  * research prototypes

---

## Key Challenges

1. **Extreme growth of exp(z)**

   * causes fast divergence
   * requires careful escape thresholds

2. **Branch cut of Log(c)**

   * discontinuity along negative real axis
   * affects visual structure

3. **Non-polynomial dynamics**

   * very different from classical Mandelbrot
   * less predictable structure

---

## Research Directions

* Is there a meaningful “connectedness locus”?
* Does EML Fractal exhibit self-similarity?
* Can we classify stable regions analytically?
* What is the role of logarithm branch choice?
* Is there a canonical normalization for EML dynamics?

---

## Stretch Ideas

* Real-time WebGL version
* AI-guided exploration of interesting regions
* Animation across parameter spaces
* 3D extensions (extra parameter dimension)

---

## Notes for Claude Code

* Prefer modular, testable components
* Keep iteration logic separate from rendering
* Make parameters easily configurable
* Add logging/debug modes for numerical issues
* Prioritize performance early (this gets expensive fast)

---

## TL;DR

We are building a Mandelbrot-like fractal based on:

```
z_{n+1} = exp(z_n) - Log(c)
```

The project sits at the intersection of:

* complex dynamics
* experimental mathematics
* visualization

Focus: make it fast, interactive, and extensible for exploration.
