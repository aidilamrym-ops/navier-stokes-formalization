# VECTOR_3 spec prose (extracted from the original .json)

The original `VECTOR_3_NAVIER_STOKES_SINGULARITY.json` contained
JSON followed by raw LaTeX prose, which made it invalid JSON.
The prose below is preserved verbatim here; the .json now contains
only the JSON object.

---

Formulasi Matematika Matriks Penegang Vortisitas ($S_{ij}$)Evolusi vortisitas 3D dalam persamaan Incompressible Navier-Stokes dikendalikan oleh interaksi antara matriks laju regangan (Rate-of-Strain Tensor) $S_{ij}$ dan vektor vortisitas $\omega_i$:$$\frac{\partial \omega_i}{\partial t} + (\vec{u} \cdot \nabla)\omega_i = S_{ij} \omega_j + \nu \nabla^2 \omega_i$$Matriks simetris $S_{ij} \in \mathbb{R}^{3 \times 3}$ didefinisikan secara eksplisit sebagai:$$S = \begin{pmatrix}  \frac{\partial u_x}{\partial x} & \frac{1}{2}\left(\frac{\partial u_x}{\partial y} + \frac{\partial u_y}{\partial x}\right) & \frac{1}{2}\left(\frac{\partial u_x}{\partial z} + \frac{\partial u_z}{\partial x}\right) \\ \frac{1}{2}\left(\frac{\partial u_y}{\partial x} + \frac{\partial u_x}{\partial y}\right) & \frac{\partial u_y}{\partial y} & \frac{1}{2}\left(\frac{\partial u_y}{\partial z} + \frac{\partial u_z}{\partial y}\right) \\ \frac{1}{2}\left(\frac{\partial u_z}{\partial x} + \frac{\partial u_x}{\partial z}\right) & \frac{1}{2}\left(\frac{\partial u_z}{\partial y} + \frac{\partial u_y}{\partial z}\right) & \frac{\partial u_z}{\partial z} \end{pmatrix}$$Kondisi batas finite-time blowup terjadi ketika nilai eigen maksimum ($\lambda_{max}$) dari matriks $S_{ij}$ sejajar sempurna dengan vektor $\omega$, sehingga menghasilkan pertumbuhan kuadratik pada intensitas penegangan:$$\lambda_{stretching} = \omega^T S \omega > 0$$
