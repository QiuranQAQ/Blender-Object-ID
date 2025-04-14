import bpy
from bpy.props import (StringProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       BoolProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       UIList,
                       )

# 定义ID集合名称
ID_COLLECTION_NAME = "ID Collection"

# 颜色属性组 - 实时更新
class ColorPropertyGroup(PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.8, 0.8, 0.8, 1.0),
        update=lambda self, context: self.update_object_color()
    )
    
    obj_ref: PointerProperty(type=bpy.types.Object)
    
    def update_object_color(self):
        if self.obj_ref:
            self.obj_ref.color = self.color[:3] + (1.0,)

# 物体列表
class OBJECT_UL_ObjectList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.obj.name, icon='OBJECT_DATA')
            row.prop(item.color, "color", text="")

# 操作符：切换ID集合视图层显示
class OBJECT_OT_ToggleIDCollectionVisibility(Operator):
    bl_idname = "object.toggle_id_collection_visibility"
    bl_label = "Toggle ID Collection Visibility"
    bl_description = "Exclude/Show ID Collection in the view layer"
    
    def execute(self, context):
        id_collection = bpy.data.collections.get(ID_COLLECTION_NAME)
        if not id_collection:
            self.report({'WARNING'}, "ID Collection not found!")
            return {'CANCELLED'}
        
        # 获取当前视图层
        view_layer = context.view_layer
        
        # 检查集合是否在视图层中
        found = False
        for layer_collection in view_layer.layer_collection.children:
            if layer_collection.collection == id_collection:
                layer_collection.exclude = not layer_collection.exclude
                found = True
                break
        
        if not found:
            self.report({'WARNING'}, "ID Collection not in view layer!")
            return {'CANCELLED'}
        
        return {'FINISHED'}

# 操作符：关联到ID子集合
class OBJECT_OT_LinkToID(Operator):
    bl_idname = "object.link_to_id"
    bl_label = "Link to ID"
    bl_description = "Associate selected objects with ID sub-collection"
    
    id_number: IntProperty(
        name="ID Number",
        description="ID number to link to (1-15)",
        min=1,
        max=15,
        default=1
    )
    
    def execute(self, context):
        # 获取或创建主ID集合
        main_collection = bpy.data.collections.get(ID_COLLECTION_NAME)
        if not main_collection:
            main_collection = bpy.data.collections.new(ID_COLLECTION_NAME)
            context.scene.collection.children.link(main_collection)
        
        # 子集合名称
        sub_coll_name = f"ID{self.id_number}"
        
        # 获取或创建子集合
        sub_collection = bpy.data.collections.get(sub_coll_name)
        if not sub_collection:
            sub_collection = bpy.data.collections.new(sub_coll_name)
            main_collection.children.link(sub_collection)
        
        # 处理选中的物体
        for obj in context.selected_objects:
            # 确保物体只在当前ID集合中
            self.ensure_only_in_id_collection(obj, sub_collection)
        
        self.report({'INFO'}, f"Associated objects with {sub_coll_name}")
        return {'FINISHED'}
    
    def ensure_only_in_id_collection(self, obj, target_collection):
        # 从所有ID集合中移除物体
        for collection in obj.users_collection:
            if collection.name.startswith("ID") and collection != target_collection:
                collection.objects.unlink(obj)
        
        # 添加到目标集合
        if target_collection.name not in [c.name for c in obj.users_collection]:
            target_collection.objects.link(obj)

# 操作符：设置集合颜色
class OBJECT_OT_SetCollectionColor(Operator):
    bl_idname = "object.set_collection_color"
    bl_label = "设置集合颜色"
    bl_description = "Set color for all objects in the collection"
    
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.8, 0.8, 0.8, 1.0)
    )
    
    def execute(self, context):
        collection_name = context.scene.my_tool.collection_name
        collection = bpy.data.collections.get(collection_name)
        
        if collection:
            for obj in collection.objects:
                obj.color = self.color[:3] + (1.0,)
            
            # 刷新列表显示
            bpy.ops.object.refresh_object_list()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        collection_name = context.scene.my_tool.collection_name
        collection = bpy.data.collections.get(collection_name)
        
        if collection and collection.objects:
            self.color = collection.objects[0].color[:3] + (1.0,)
        
        return context.window_manager.invoke_props_dialog(self)

# 操作符：刷新物体列表
class OBJECT_OT_RefreshObjectList(Operator):
    bl_idname = "object.refresh_object_list"
    bl_label = "Refresh Object List"
    bl_description = "Refresh the list of objects in the selected collection"
    
    def execute(self, context):
        scene = context.scene
        mytool = scene.my_tool
        collection = bpy.data.collections.get(mytool.collection_name)
        
        mytool.object_items.clear()
        
        if collection:
            for obj in collection.objects:
                item = mytool.object_items.add()
                item.obj = obj
                item.color.color = obj.color[:3] + (1.0,)
                item.color.obj_ref = obj  # 设置对象引用用于实时更新
        
        return {'FINISHED'}

# 物体列表项
class ObjectListItem(PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)
    color: PointerProperty(type=ColorPropertyGroup)

# 主工具属性
class MyToolProperties(PropertyGroup):
    collection_name: StringProperty(
        name="Collection",
        description="Select a collection to modify",
        default=""
    )
    object_items: bpy.props.CollectionProperty(type=ObjectListItem)
    active_object_index: IntProperty(default=0)
    hide_id_collection: BoolProperty(
        name="Hide ID Collection",
        description="Exclude ID Collection from view layer",
        default=False,
        update=lambda self, context: self.update_id_collection_visibility(context)
    )
    
    def update_id_collection_visibility(self, context):
        id_collection = bpy.data.collections.get(ID_COLLECTION_NAME)
        if not id_collection:
            return
        
        view_layer = context.view_layer
        for layer_collection in view_layer.layer_collection.children:
            if layer_collection.collection == id_collection:
                layer_collection.exclude = self.hide_id_collection
                break

# 面板
class OBJECT_PT_ColorPanel(Panel):
    bl_label = "Object ID 0.1 By 叱咤月海鱼鱼猫"
    bl_idname = "OBJECT_PT_color_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Object ID"
    
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool
        
        # 集合选择和刷新按钮
        row = layout.row()
        row.prop_search(mytool, "collection_name", bpy.data, "collections", text="Collection")
        row.operator("object.refresh_object_list", text="", icon='FILE_REFRESH')
        
        # 集合颜色设置
        row = layout.row()
        row.operator("object.set_collection_color", text="Set Collection Color")
        
        # 物体列表
        layout.template_list("OBJECT_UL_ObjectList", "", mytool, "object_items", mytool, "active_object_index")
        
        # ID集合部分
        layout.separator()
        box = layout.box()
        box.label(text="ID Channel")
        
        # ID集合可见性切换
        row = box.row()
        row.prop(mytool, "hide_id_collection", toggle=True, 
                text="˃.˂这样就不影响渲染辣" if mytool.hide_id_collection else "@_@请点这里隐藏ID集合", 
                icon='HIDE_ON' if mytool.hide_id_collection else 'HIDE_OFF')
        
        # ID子集合按钮
        row = box.row()
        for i in range(1, 6):
            row.operator("object.link_to_id", text=f"ID{i}").id_number = i
        
        row = box.row()
        for i in range(6, 11):
            row.operator("object.link_to_id", text=f"ID{i}").id_number = i
        
        row = box.row()
        for i in range(11, 16):
            row.operator("object.link_to_id", text=f"ID{i}").id_number = i

# 注册
classes = (
    ColorPropertyGroup,
    ObjectListItem,
    MyToolProperties,
    OBJECT_UL_ObjectList,
    OBJECT_OT_ToggleIDCollectionVisibility,
    OBJECT_OT_LinkToID,
    OBJECT_OT_SetCollectionColor,
    OBJECT_OT_RefreshObjectList,
    OBJECT_PT_ColorPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_tool = PointerProperty(type=MyToolProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.my_tool

if __name__ == "__main__":
    register()