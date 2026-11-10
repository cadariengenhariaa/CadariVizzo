"""Captura uma imagem 3D (PNG) de uma interferência específica — os dois
elementos destacados por cor, câmera enquadrada automaticamente.

Usa um vtkRenderWindow OFF-SCREEN (nenhuma janela abre na tela),
construído a partir das malhas já extraídas (`ElementoClash.malha`) — um
pacote isolado, não depende do `IFCViewerFrame` nem reabre o IFC. A
construção do vtkPolyData segue o mesmo padrão comprovado em
`ifc_viewer.py` (`ImportLegacyFormat`, não `SetCells`, que não
funcionou nesta versão do VTK)."""
import numpy as np
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

from clash.geometria import malha_por_guid

COR_ELEMENTO_A = (0.94, 0.35, 0.35)  # vermelho
COR_ELEMENTO_B = (0.33, 0.55, 0.95)  # azul


class _ElementoComMalha:
    """Wrapper mínimo só para dar `.malha` a `capturar_snapshot` sem
    precisar de um `ElementoClash` completo."""

    def __init__(self, malha):
        self.malha = malha


def _malha_para_actor(malha, cor):
    pontos = vtk.vtkPoints()
    pontos.SetData(numpy_to_vtk(np.asarray(malha.vertices, dtype=np.float64), deep=True))

    n_tri = len(malha.faces)
    conectividade = np.hstack(
        [np.full((n_tri, 1), 3, dtype=np.int64), np.asarray(malha.faces, dtype=np.int64)]
    ).ravel()
    id_array = numpy_to_vtkIdTypeArray(conectividade, deep=True)
    celulas = vtk.vtkCellArray()
    celulas.ImportLegacyFormat(id_array)

    polydata_bruto = vtk.vtkPolyData()
    polydata_bruto.SetPoints(pontos)
    polydata_bruto.SetPolys(celulas)

    normais = vtk.vtkPolyDataNormals()
    normais.SetInputData(polydata_bruto)
    normais.ComputeCellNormalsOn()
    normais.ComputePointNormalsOff()
    normais.SplittingOff()
    normais.Update()

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(normais.GetOutput())

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*cor)
    return actor


def capturar_snapshot(elemento_a, elemento_b, caminho_png, largura=800, altura=600):
    """Renderiza `elemento_a` (vermelho) e `elemento_b` (azul) sozinhos
    numa cena off-screen, câmera enquadrando os dois, e grava um PNG em
    `caminho_png`. Retorna o próprio `caminho_png`."""
    vtk.vtkObject.GlobalWarningDisplayOff()

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.94, 0.95, 0.96)
    renderer.AddActor(_malha_para_actor(elemento_a.malha, COR_ELEMENTO_A))
    renderer.AddActor(_malha_para_actor(elemento_b.malha, COR_ELEMENTO_B))

    render_window = vtk.vtkRenderWindow()
    render_window.SetOffScreenRendering(1)
    render_window.AddRenderer(renderer)
    render_window.SetSize(largura, altura)

    renderer.ResetCamera()
    renderer.GetActiveCamera().Zoom(0.85)  # uma folga ao redor dos elementos
    render_window.Render()

    capturador = vtk.vtkWindowToImageFilter()
    capturador.SetInput(render_window)
    capturador.Update()

    escritor = vtk.vtkPNGWriter()
    escritor.SetFileName(caminho_png)
    escritor.SetInputConnection(capturador.GetOutputPort())
    escritor.Write()

    return caminho_png


def capturar_snapshot_do_clash(clash, arquivos_ifc, escala_por_arquivo, caminho_png, settings=None,
                                largura=800, altura=600):
    """Conveniência para o relatório: recebe um dict de interferência
    (como salvo em `db_clashes.json`, só com guid/classe/nome dos
    elementos — não a malha) e os arquivos IFC já abertos, recria as duas
    malhas pelo GUID e captura o snapshot. Se um dos arquivos de origem
    não estiver mais disponível (ex.: relatório gerado numa máquina sem
    acesso à rede), devolve None em vez de falhar o relatório inteiro."""
    info_a, info_b = clash["elemento_a"], clash["elemento_b"]
    try:
        ifc_a = arquivos_ifc[info_a["arquivo"]]
        ifc_b = arquivos_ifc[info_b["arquivo"]]
        malha_a = malha_por_guid(ifc_a, info_a["guid"], escala_por_arquivo.get(info_a["arquivo"], 1.0), settings)
        malha_b = malha_por_guid(ifc_b, info_b["guid"], escala_por_arquivo.get(info_b["arquivo"], 1.0), settings)
    except Exception:
        return None

    return capturar_snapshot(_ElementoComMalha(malha_a), _ElementoComMalha(malha_b), caminho_png,
                              largura=largura, altura=altura)
