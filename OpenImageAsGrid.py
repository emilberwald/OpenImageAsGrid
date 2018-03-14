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

	directory = bpy.props.StringProperty(subtype="DIR_PATH")
	files = bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
	
	loop_order = bpy.props.EnumProperty(
		name="loop_order",
		default='x',
		items=[
			('x', "x-major",
			 "The outer loop of the polygon search will be over the x-axis."),
			('y', "y-major",
			 "The outer loop of the polygon search will be over the y-axis.")
		],
		description="What the outer loop of the polygon search should iterate over.")

	rgba_min = bpy.props.FloatVectorProperty(
		name="rgba_min",
		min=0.0,
		soft_min=0.0,
		max=1.0,
		soft_max=1.0,
		default=(0.0, 0.0, 0.0, 0.0),
		size=4,
		description="Lower limit for inclusion. (r,g,b,a)")

	rgba_min_inclusive = bpy.props.BoolVectorProperty(
		name="rgba_min_inclusive",
		default=(True, True, True, False),
		size=4,
		description="Whether the lower limit is inclusive (<=) or not (<). (r,g,b,a)")

	rgba_max = bpy.props.FloatVectorProperty(
		name="rgba_max",
		min=0.0,
		soft_min=0.0,
		max=1.0,
		soft_max=1.0,
		default=(1.0, 1.0, 1.0, 1.0),
		size=4,
		description="Upper limit (r,g,b,a).")

	rgba_max_inclusive = bpy.props.BoolVectorProperty(
		name="rgba_max_inclusive",
		default=(True, True, True, True),
		size=4,
		description="Whether the upper limit is inclusive (<=) or not (<). (r,g,b,a)")

	polygon_align_length = bpy.props.IntVectorProperty(name="polygon_align_length", description="Polygon alignment (x,y).", default=(1,1),size=2, min=1, max=2**31-1, soft_min=1, soft_max=2**31-1, step=1)

	def draw_algorithm_config(self, context):
		layout = self.layout
		box = layout.box()
		box.label("Algorithm configuration:", icon='SNAP_GRID')
		col = box.column()
		row = col.row()
		row.prop(self, "loop_order", expand=True)
		row = col.row()
		row.prop(self, "polygon_align_length", expand=True)
		row = col.row()
		row.prop(self, "rgba_min", expand=True)
		row = col.row()
		row.prop(self, "rgba_min_inclusive", expand=True)
		row = col.row()
		row.prop(self, "rgba_max", expand=True)
		row = col.row()
		row.prop(self, "rgba_max_inclusive", expand=True)

	def draw(self, context):
		self.draw_algorithm_config(context)

	@staticmethod
	def get_rgba(pixels, offset, x, y):
		return [
			pixels[4 * (int(round(x) + int(round(y)) * offset)) + i]
			for i in range(0, 4)
		]

	@staticmethod
	def add_vertices_and_face_to_mesh(bm, image, p0,polygonAlignLength : int, okPositions: set, global_vlist:dict):
		def S(x):
			return [1.0 / float(image.size[k]) * x[k] for k in [0, 1]] + [0]
		if p0 in okPositions:
			xroi = list()
			yroi = list()
			xroi.append(p0[0])
			yroi.append(p0[1])
			for k in range(0, min(image.size[0], image.size[1])//max(polygonAlignLength)):
				xroit = range(p0[0], p0[0] + k*polygonAlignLength[0])
				yroit = range(p0[1], p0[1] + k*polygonAlignLength[1])
				if {(x, y) for x in xroit for y in yroit} & okPositions:
					xroi = xroit
					yroi = yroit
				else:
					break
			if (xroi and yroi):
				xlims = [min(xroi), max(xroi)+polygonAlignLength[0]]
				ylims = [min(yroi), max(yroi)+polygonAlignLength[1]]
				local_vlist = list()
				for (xt, yt) in [(xlims[0], ylims[0]), (xlims[1], ylims[0]),
								 (xlims[1], ylims[1]), (xlims[0], ylims[1])]:
					if (xt,yt) not in global_vlist.keys():
						global_vlist[(xt,yt)] = bm.verts.new(S([xt, yt, 0]))
					local_vlist.append(global_vlist[(xt,yt)])
				for k in range(0,len(local_vlist)):
					local_vpair = (local_vlist[(k)%(len(local_vlist))],local_vlist[(k+1)%(len(local_vlist))])
					if bm.edges.get(local_vpair) is None:
						bm.edges.new(local_vpair)
				bm.faces.new(local_vlist)
				okPositions.difference_update({(x, y)
											   for x in xroi for y in yroi})

	def add_vertices_and_faces_to_mesh(self, mesh, image):
		"""Not sure how the layout of the image is in blender..."""
		rgba_min = self.rgba_min[:]
		rgba_min_inclusive = self.rgba_min_inclusive[:]
		rgba_max = self.rgba_max[:]
		rgba_max_inclusive = self.rgba_max_inclusive[:]
		def should_be_included(pixels, offset, x, y):
			rgba = OpenImageAsGrid.get_rgba(pixels, offset, x, y)
			return all([
				all([
					rgba_min[k] <= rgba[k] if rgba_min_inclusive[k]
					else rgba_min[k] < rgba[k] for k in range(0, 4)
				]),
				all([
					rgba[k] <= rgba_max[k] if rgba_max_inclusive[k]
					else rgba[k] < rgba_max[k] for k in range(0, 4)
				])])

		bm = bmesh.new()
		pixels = image.pixels[:]
		offset = image.size[0]
		okPositions = set()
		okPositions.update({(x, y)
							for x in range(0, image.size[0], 1)
							for y in range(0, image.size[1], 1)
							if should_be_included(pixels, offset, x, y)})
		global_vlist = dict()
		if (self.loop_order == "x"):
			for x in range(0, image.size[0], self.polygon_align_length[0]):
				for y in range(0, image.size[1], self.polygon_align_length[1]):
					OpenImageAsGrid.add_vertices_and_face_to_mesh(
						bm, image,(x, y),self.polygon_align_length, okPositions, global_vlist)
		elif (self.loop_order == "y"):
			for y in range(0, image.size[1], self.polygon_align_length[0]):
				for x in range(0, image.size[0], self.polygon_align_length[1]):
					OpenImageAsGrid.add_vertices_and_face_to_mesh(
						bm, image,(x, y),self.polygon_align_length, okPositions,global_vlist)
		else:
			raise ValueError(
				"The selected loop_order ({loop_order}) is not supported.".
				format(loop_order=self.loop_order))
		bm.to_mesh(mesh)
		bm.free()

	def create_mesh_from_opaque_pixels(self, postfixName, image):
		print(inspect.getframeinfo(inspect.currentframe()))
		mesh = bpy.data.meshes.new(
			"mesh-{postfixName}".format(postfixName=postfixName))
		obj = bpy.data.objects.new(
			"object-{postfixName}".format(postfixName=postfixName), mesh)
		bpy.context.scene.objects.link(obj)
		bpy.context.scene.update()
		bpy.context.scene.objects.active = obj
		obj.select = True
		self.add_vertices_and_faces_to_mesh(
			bpy.context.object.data, image)
		print(inspect.getframeinfo(inspect.currentframe()))

	def import_image(self, context,filepath):
		def get_image_texture(filepath,imageName):
			imageTexture = bpy.data.textures.new(
				"tex-{postfixName}".format(postfixName=imageName), 'IMAGE')
			imageTexture.image = bpy.data.images.load(
				filepath, check_existing=True)
			imageTexture.extension = 'EXTEND'
			return imageTexture

		def get_image_material(imageName):
			imageMaterial = bpy.data.materials.new(
				"mat-{postfixName}".format(postfixName=imageName))
			imageMaterial.use_transparency = True
			imageMaterial.alpha = 0
			imageMaterial.transparency_method = 'MASK'
			return imageMaterial

		def get_mesh_texture_poly_layer(imageName):
			meshTexturePolyLayer = bpy.context.object.data.uv_textures.new(
				name="uv-{postfixName}".format(postfixName=imageName))
			for poly in bpy.context.object.data.polygons:
				for loop_index in poly.loop_indices:
					vertex_index = bpy.context.object.data.loops[
						loop_index].vertex_index
					vertex = bpy.context.object.data.vertices[vertex_index].co
					bpy.context.object.data.uv_layers.active.data[
						loop_index].uv = vertex[:-1]
			# meshTexturePolyLayer.data[0].image = imageTexture.image
			return meshTexturePolyLayer

		def new_image_material_texture_slot(imageMaterial, imageTexture,
											meshTexturePolyLayer):
			materialTextureSlot = imageMaterial.texture_slots.add()
			materialTextureSlot.texture = imageTexture
			materialTextureSlot.use_map_alpha = True
			materialTextureSlot.texture_coords = 'UV'
			materialTextureSlot.uv_layer = meshTexturePolyLayer.name
			materialTextureSlot.mapping = 'FLAT'
			return materialTextureSlot

		imageName = Path(filepath).stem
		imageTexture = get_image_texture(filepath,imageName)
		imageMaterial = get_image_material(imageName)
		self.create_mesh_from_opaque_pixels(imageName, imageTexture.image)
		meshTexturePolyLayer = get_mesh_texture_poly_layer(imageName)
		materialTextureSlot = new_image_material_texture_slot(
			imageMaterial, imageTexture, meshTexturePolyLayer)
		bpy.context.object.data.materials.append(imageMaterial)
		print(inspect.getframeinfo(inspect.currentframe()))
		# A mesh has several polygons. Each polygon has unique identifiers for its vertices, loop_indices. Each loop_index maps to a vertex, to an edge(vertex + vertex), to a 2D UV-coordinate.
		#(my research indicates that) unwrapping is finding nice UV-coordinates for the vertices in the polygons in the mesh.
		# bpy.ops.object.mode_set(mode='EDIT')
		# bpy.ops.uv.unwrap(method='CONFORMAL', fill_holes=True, correct_aspect=False, use_subsurf_data=False, margin=0.0)
		# bpy.ops.object.mode_set(mode='OBJECT')
		# print(inspect.getframeinfo(inspect.currentframe()))

	def execute(self, context):
		for file in self.files:
			self.import_image(context,str(Path(self.directory).joinpath(file.name)))
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


# Only needed if you want to add into a dynamic menu
def open_image_as_grid_menu(self, context):
	self.layout.operator(
		OpenImageAsGrid.bl_idname, text="Open image as grid", icon='IMAGE_RGB')


def register():
	bpy.utils.register_class(OpenImageAsGrid)
	bpy.types.INFO_MT_file_import.append(open_image_as_grid_menu)


def unregister():
	bpy.types.INFO_MT_file_import.remove(open_image_as_grid_menu)
	bpy.utils.unregister_class(OpenImageAsGrid)
