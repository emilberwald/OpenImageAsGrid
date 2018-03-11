bl_info = {
    "name": "Open Image as Grid",
    "author": "Emil Berwald",
    "version": (0, 0, 1),
    "blender": (2, 79, 0),
    "location": "File > Import > Open Image as Grid",
    "description": "Open an image, create grid and material & texture",
    "warning": "",
    "wiki_url": "(N/A)",
    "category": "Import-Export",
}

import inspect 
import bpy
import bmesh
from pathlib import Path

class OpenImageAsGrid(bpy.types.Operator):
	"""Opens an image and adds it as a grid with a material and a texture"""
	bl_idname = "openimage.as_grid"
	bl_label = "Open Image as Grid"
	bl_options = {'REGISTER'}

	filepath = bpy.props.StringProperty(subtype="FILE_PATH")

	@staticmethod
	def get_rgba(pixels,offset, x, y):
		return [pixels[4*(int(round(x)+int(round(y))*offset))+i] for i in range(0,4)]
	
	@staticmethod
	def find_ylims(pixels,offset,x,yrange):
		ylims = [max(yrange),min(yrange)]
		roi = False
		for y in yrange:
			if(OpenImageAsGrid.get_rgba(pixels,offset,x,y)[3]>0):
				if(not roi):
					roi = True
				if(roi):
					ylims[0] = min(ylims[0],y)
					ylims[1] = max(ylims[1],y)
			else:
				if (roi):
					break
		if(roi):
			return ylims
		else:
			return None
	@staticmethod
	def add_vertices_edges_faces_to_mesh(mesh,image, suggestedNofSteps=None):
		"""Not sure how the layout of the image is in blender..."""
		suggestedNofSteps = max(image.size[0],image.size[1]) if suggestedNofSteps is None else suggestedNofSteps
		print(inspect.getframeinfo(inspect.currentframe()))
		bm = bmesh.new()
		stepsize = [max(1,image.size[k]//suggestedNofSteps) for k in range(0,len(image.size))]
		def S(x):
			return [1.0/float(image.size[k])*x[k] for k in [0,1]]+[0]
		pixels = image.pixels[:]
		offset = image.size[0]
		print("Uses stepsize:{0}".format(stepsize))
		for x in range(0,image.size[0],stepsize[0]):
			yrange = range(0,image.size[1],stepsize[1])
			while(len(yrange)>0):
				xlims = [x,x+stepsize[0]]
				ylims = OpenImageAsGrid.find_ylims(pixels,offset,x,yrange)
				if(ylims):
					local_vlist = list()
					for (xt,yt) in [(xlims[0],ylims[0]),(xlims[0],ylims[1]),(xlims[1],ylims[1]),(xlims[0],ylims[1])]:
						local_vlist.append(bm.verts.new(S([xt,yt,0])))
					bm.faces.new( local_vlist )
					for k in range(0,len(local_vlist)):
						local_vpair = (local_vlist[(k)%(len(local_vlist))],local_vlist[(k+1)%(len(local_vlist))])
						if bm.edges.get(local_vpair) is None:
							bm.edges.new(local_vpair)
					yrange = range(ylims[1]+stepsize[1],image.size[1],stepsize[1])
				else:
					break
		print(inspect.getframeinfo(inspect.currentframe()))

		# uv_layer = bm.loops.layers.uv.verify()
		# bm.faces.layers.tex.verify()
		# for f in bm.faces:
		# 	for l in f.loops:
		# 		luv = l[uv_layer]

		bm.to_mesh(mesh)
		bm.free()
		print(inspect.getframeinfo(inspect.currentframe()).lineno)

	@staticmethod
	def create_mesh_from_opaque_pixels(postfixName, image):
		print(inspect.getframeinfo(inspect.currentframe()))
		mesh = bpy.data.meshes.new("mesh-{postfixName}".format(postfixName=postfixName))
		obj = bpy.data.objects.new("object-{postfixName}".format(postfixName=postfixName),mesh)
		bpy.context.scene.objects.link(obj)
		bpy.context.scene.update()
		bpy.context.scene.objects.active = obj
		obj.select = True
		OpenImageAsGrid.add_vertices_edges_faces_to_mesh(bpy.context.object.data,image)
		print(inspect.getframeinfo(inspect.currentframe()))


	def execute(self, context):
		print(inspect.getframeinfo(inspect.currentframe()))
		imageName = Path(self.filepath).stem

		imageTexture = bpy.data.textures.new("tex-{postfixName}".format(postfixName=imageName),'IMAGE')
		imageTexture.image = bpy.data.images.load(self.filepath, check_existing=True)
		imageTexture.extension = 'EXTEND'
		print(inspect.getframeinfo(inspect.currentframe()))

		imageMaterial = bpy.data.materials.new("mat-{postfixName}".format(postfixName=imageName))
		imageMaterial.use_transparency = True
		imageMaterial.alpha = 0
		imageMaterial.transparency_method = 'MASK'
		print(inspect.getframeinfo(inspect.currentframe()))

		OpenImageAsGrid.create_mesh_from_opaque_pixels(imageName,imageTexture.image)
		print(inspect.getframeinfo(inspect.currentframe()))

		meshTexturePolyLayer = bpy.context.object.data.uv_textures.new(name="uv-{postfixName}".format(postfixName=imageName))
		for poly in bpy.context.object.data.polygons:
			for loop_index in poly.loop_indices:
				vertex_index = bpy.context.object.data.loops[loop_index].vertex_index
				vertex=bpy.context.object.data.vertices[vertex_index].co
				bpy.context.object.data.uv_layers.active.data[loop_index].uv=vertex[:-1]
		print(inspect.getframeinfo(inspect.currentframe()))
		# meshTexturePolyLayer.data[0].image = imageTexture.image

		materialTextureSlot = imageMaterial.texture_slots.add()
		materialTextureSlot.texture = imageTexture
		materialTextureSlot.use_map_alpha = True
		materialTextureSlot.texture_coords = 'UV'
		materialTextureSlot.uv_layer = meshTexturePolyLayer.name
		materialTextureSlot.mapping = 'FLAT'
		print(inspect.getframeinfo(inspect.currentframe()))
		
		bpy.context.object.data.materials.append(imageMaterial)
		print(inspect.getframeinfo(inspect.currentframe()))
		
		#A mesh has several polygons. Each polygon has unique identifiers for its vertices, loop_indices. Each loop_index maps to a vertex, to an edge(vertex + vertex), to a 2D UV-coordinate.
		#(my research indicates that) unwrapping is finding nice UV-coordinates for the vertices in the polygons in the mesh.
		#bpy.ops.object.mode_set(mode='EDIT')
		#bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=True, correct_aspect=False, use_subsurf_data=False, margin=0.0)
		#bpy.ops.object.mode_set(mode='OBJECT')
		#print(inspect.getframeinfo(inspect.currentframe()))
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


# Only needed if you want to add into a dynamic menu
def open_image_as_grid_menu(self, context):
	self.layout.operator(OpenImageAsGrid.bl_idname, text="Open image as grid",icon='IMAGE_RGB')

def register():
	bpy.utils.register_class(OpenImageAsGrid)
	bpy.types.INFO_MT_file_import.append(open_image_as_grid_menu)

def unregister():
	bpy.types.INFO_MT_file_import.remove(open_image_as_grid_menu)
	bpy.utils.unregister_class(OpenImageAsGrid)
