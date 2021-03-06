import os
import numpy as np
from OpenGL.GL import *
from PIL.Image import open as pilopen


class DisplayObj:
    def __init__(self, verts=None, norms=None, edges=None, surfs=None, uvs=None, cols=None, nam=None, mats=None):
        self.verts = verts  # vertex list
        self.norms = norms  # vertex norm list
        self.edges = edges  # edge list
        self.surfs = surfs  # surface, surface uv, surface norm
        self.uvs = uvs      # uv map points
        self.cols = cols    # color list, parallel with surface
        self.name = nam     # name
        self.mats = mats    # Materials: hashmap materialname -> Material
        self.maxr = 0       # max radius
        self.scale = 1.0    # scale
        self.curdir = None  # current directory

        self.dlindex = -1   # display list index

        self.usetex = False # use texture
        self.texfile = None # Texture file
        self.texindex = -1  # texture list index

    def objFileImport(self, objName):
        # Init vars
        objFname = objName + ".obj"
        curmat = None

        # Reset current ivars
        self.verts = []
        self.norms = []
        self.edges = []
        self.surfs = []
        self.cols = []
        self.uvs = []
        self.mats = None
        self.usetex = False

        if not os.path.exists(objFname):
            raise FileNotFoundError(objFname + " does not exist!")

        self.curdir = os.path.dirname(os.path.abspath(objFname))

        # Read in verts, edges, and surfs
        with open(objFname) as fp:
            line = fp.readline()
            while line:
                args = line.strip().split(" ")  # get line args
                cmd = args[0]

                if cmd == "mtllib": # mtl library
                    mtlFname = os.path.join(self.curdir,args[1])
                    if not os.path.exists(mtlFname):
                        raise FileNotFoundError(mtlFname + " referenced but does not exist!")
                    self.mats = self.loadMats(mtlFname)
                elif cmd == "o": # object name
                    self.name = args[1]
                elif cmd == "v": # vertex
                    vert = (float(args[1]),float(args[2]),float(args[3]))
                    self.verts.append(vert)
                    sum_squares = sum(map(lambda a: a*a, vert))
                    if self.maxr < sum_squares:
                        self.maxr = sum_squares
                elif cmd == "vn": # vertex normal
                    self.norms.append((float(args[1]),float(args[2]),float(args[3])))
                elif cmd == "vt": # vertex texture
                    self.uvs.append((float(args[1]),float(args[2])))
                elif cmd == "usemtl": # use material
                    curmat = args[1]
                elif cmd == "f": # face
                    self.loadFaceCmd(args[1:])
                    if self.mats and curmat: # if we have a material to load...
                        self.cols.append(curmat)
                line = fp.readline()
            self.maxr = np.sqrt(self.maxr)

    def loadFaceCmd(self, args):
        # EDGES
        vertlist = []
        texlist = []
        tmp = None
        for arg in args:
            tmp = arg.split("/")
            vertlist.append( int(tmp[0])-1 ) # append the vertex number (first number in str) -1 to make index
            if tmp[1]:
                texlist.append( int(tmp[1])-1 ) # append the tex number if it exists
            else:
                texlist.append(0)

        norm = int(tmp[2])-1 # grab the vertex normal number

        for i in range(len(vertlist) - 1):
            edge = (vertlist[i],vertlist[i+1])  # get edge of face
            if edge not in self.edges and (edge[1],edge[0]) not in self.edges: # if we don't have a copy of this yet...
                self.edges.append(edge)

        edge = (vertlist[-1],vertlist[0])  # append last and first
        if edge not in self.edges and (edge[1], edge[0]) not in self.edges:  # if we don't have a copy of this yet...
            self.edges.append(edge)

        # FACE
        self.surfs.append((tuple(vertlist), tuple(texlist), norm))

    def loadMats(self, fname):
        # Init vars
        mats = {}
        curmat = None

        with open(fname) as fp:
            line = fp.readline()
            while line:
                args = line.strip().split(" ")  # Split arguments on space after removing \n from end
                cmd = args[0]  # command is always the first arg

                if cmd == "newmtl":  # new material
                    curmat = args[1]
                    mats[curmat] = Material()
                # elif cmd == "Ka": # ambient color
                #     mats[curmat].amb = (float(args[1]),float(args[2]),float(args[3]))
                elif cmd == "Kd":  # diffuse color
                    mats[curmat].amb = (float(args[1]), float(args[2]), float(args[3]))
                    mats[curmat].diff = (float(args[1]), float(args[2]), float(args[3]))
                elif cmd == "Ks":  # diffuse color
                    mats[curmat].spec = (float(args[1]), float(args[2]), float(args[3]))
                elif cmd == "Ke":  # diffuse color
                    mats[curmat].emm = (float(args[1]), float(args[2]), float(args[3]))
                elif cmd == "d":  # transparency
                    mats[curmat].trans = float(args[1])
                elif cmd == "map_Kd": # texture map
                    self.usetex = True
                    self.register_texture(args[1])
                else:  # anything else
                    pass

                line = fp.readline()

        return mats

    def register_texture(self, fname):
        im = pilopen(os.path.join(self.curdir,fname))
        try:
            ix, iy, image = im.size[0], im.size[1], im.tobytes("raw", "RGB", 0, -1)
        except SystemError:
            ix, iy, image = im.size[0], im.size[1], im.tobytes("raw", "RGBX", 0, -1)
        self.texindex = glGenTextures(1)                # generate texture index
        glBindTexture(GL_TEXTURE_2D, self.texindex)     # bind the texture
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)           # set the pixel store to unpack alignment
        glTexImage2D(                                   # load the texture
            GL_TEXTURE_2D, 0, 3, ix, iy, 0,
            GL_RGB, GL_UNSIGNED_BYTE, image
        )

    def drawObj(self):
        if self.dlindex == -1:  # Immediate mode
            glScalef(self.scale, self.scale, self.scale)
            for col, vertex_uv_norm in zip(self.cols, self.surfs): # for the color, surface, surface_norm
                mat = self.mats[col] if col in self.mats else Material()
                # Set material properties
                if not self.usetex:
                    glMaterialfv(GL_FRONT, GL_AMBIENT, mat.amb)
                    glMaterialfv(GL_FRONT, GL_DIFFUSE, mat.diff)
                    glMaterialfv(GL_FRONT, GL_SPECULAR, mat.spec)
                    glMaterialfv(GL_FRONT, GL_EMISSION, mat.emm)

                surface = vertex_uv_norm[0] # surface verticies
                uv = vertex_uv_norm[1]      # uv points
                norm = vertex_uv_norm[2]    # surface norm
                if len(surface) == 3:   # if there are 3 verticies...
                    glBegin(GL_TRIANGLES)
                elif len(surface) == 4: # if there are 4 verticies...
                    glBegin(GL_QUADS)
                else:                   # if there are more than 5 verticies...
                    glBegin(GL_POLYGON)
                glNormal3fv(self.norms[norm])
                for vertex, uv in zip(surface,uv):
                    if self.usetex:
                        glTexCoord2f(*self.uvs[uv])
                    glVertex3fv(self.verts[vertex])
                glEnd()
            glScalef(1.0,1.0,1.0)

            # glBegin(GL_LINES)
            # glColor3fv((0.0, 0.0, 0.0))
            # for edge in self.edges:
            #     for vertex in edge:
            #         glVertex3fv(self.verts[vertex])
            # glEnd()
        else: # Display List
            if self.usetex:
                # Texture init
                glEnable(GL_TEXTURE_2D)
                glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
                glTexParameter(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
                glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_DECAL)
                glBindTexture(GL_TEXTURE_2D, self.texindex)
            glCallList(self.dlindex)
            if self.usetex:
                glDisable(GL_TEXTURE_2D)

    def register(self, extraFunc=None):
        index = glGenLists(1)
        glNewList(index,GL_COMPILE)
        self.drawObj()
        if extraFunc:
            extraFunc()
        glEndList()
        self.dlindex = index

    def deregister(self):
        glDeleteLists(self.dlindex, 1)


class Material:
    def __init__(self, amb=(0.2,0.2,0.2,1.0), diff=(0.8,0.8,0.8,0.8), spec=(0.0,0.0,0.0,1.0), emm=(0.0,0.0,0.0,1.0), trans=1.0):
        self.amb   = amb
        self.diff  = diff
        self.spec  = spec
        self.emm   = emm
        self.trans = trans

    def set_dse(self,d,s,e):
        self.amb = d
        self.diff = d
        self.spec = s
        self.emm  = e
