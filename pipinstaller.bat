@echo off
echo Pip guncelleniyor...
python -m pip install --upgrade pip

echo Gerekli paketler kuruluyor...

pip install --upgrade keyboard
pip install --upgrade pynput
pip install --upgrade pymem
pip install --upgrade pywin32
pip install --upgrade "imgui[full]"
pip install --upgrade glfw
pip install --upgrade PyOpenGL PyOpenGL_accelerate
pip install --upgrade requests
pip install --upgrade git+https://github.com/TomSchimansky/CustomTkinter
pip install --upgrade PyQt5
pip install --upgrade pillow
pip install --upgrade numpy

echo Tum paketler kuruldu ve guncellendi.
pause
