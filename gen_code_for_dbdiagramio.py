"""
This script is for service in https://dbdiagram.io to create DBML code for 
drawing db design and reads Django's models.py for generating database 
model of it, over schema limits.

Usage:
    python3 gen_code_for_dbdiagamio.py [-s] [-c views starting tag] [--user] models-file

The models which are views should be place to the end of models.py.

Toni Patama, topat047@gmail.com
"""

import sys
import re
import os.path

def scan_main_blocks(lines, views_start_kw, user_table_def):
    """ 
    Parse models.py classes and make cleaned list of Django models
    
    Last commandline option after filename is string which should start commenting code:
    
        gen_code_for_dbdiagamio -c "# Views" --user models.py 
    
    Here models which actually are views - not tables - are referred starting with comment: "# Views". This affects all the models
    after this comment. So exceptions should be put last in models.py
 
    
    """
    code_blocks = []
    code_block_list = []

    # generate Django default user table for having minimum requirements
    # when it is not defined in the models.py
    if user_table_def['include']:
        usertabcode = []
        usertabcode.append("class User(models.Model):")
        usertabcode.append("    username = model.CharField(length=255)")
        usertabcode.append(f"        db_table = {user_table_def['table_name']}")
        code_blocks.append(usertabcode)
    
    for line in lines:
        # if not comment line
        if not re.match("^\s*(#{1,}.*)$",line) : #or not re.match("^\s*#.*$"):
            #print(line)

            # begin class of django model
            if re.match("^class .+(models\.Model)",line):
                #print(line)

                # Save collected rows to one code block before adding new rows of the new class
                if len(code_block_list):
                    code_blocks.append(code_block_list)
                    code_block_list = []
                code_block_list.append(line)
              

            # stop collecting rows if class or def is opened but it is not part of models
            # classes and defs can appear inside the model class so this happeneds only when 
            # they appear in the beginning of the row
            elif re.match("^(class|def) .+", line) and len(code_block_list):
                    code_blocks.append(code_block_list)
                    code_block_list = []

            elif len(code_block_list)>0 and len(line):
                code_block_list.append(line)
                #print(line)
                 # + "\n"
        elif len(views_start_kw) and re.match(f".*{views_start_kw}.*", line):
            #start commenting for views (not table structure)
            #print("/*" + line)
            code_block_list.append("/* " + line)
    else: 
        # Finally add last code_block_list to code_blocks
        code_blocks.append(code_block_list)
    
    if len(views_start_kw):
        ## add end of commenting to last block
        code_blocks[-1].append(views_start_kw + " */")

    # debug: how many models are included?
    #print(len(code_blocks))
    return code_blocks

def analyze_block(block_code_list, views_start_kw):
    """
    Analyse and parse code blocks to extract essential info of the models, like model name, table name and 
    field list with definitions
    """
    def parse_model_name(line):
         return line.replace("class ","").replace("(models.Model):","").strip()
    
    #def parse_field_name_type(line):
        
        
    def default_indentation(code_block_lines):
        for line in code_block_lines[1:]:
            if not re.match("^\s*(#{1,}.*)$",line):
                count = 0
                intent = ""
                for letter in line:
                    if letter == "\t":
                        return letter
                    else:
                        if letter == " ":
                            intent += letter
                        else:
                            return intent

    table_name = ""
    model_name = ""
    fields_dict = []
    intent_type = default_indentation(block_code_list)
    include_view = ""
    
    for line in block_code_list:
        if re.match("^class .+(models\.Model)",line):
            model_name = parse_model_name(line)
            empty_space_index = block_code_list[1].index(" ")
        elif re.match(f"^{intent_type}\w+\s*=( *)models.+", line):
            # field row: parse field name and field type, if foreign key, parse model reference
            field_name = ""
            for letter in line[len(intent_type):]:
                if re.match("\w",letter):
                    field_name += letter
                elif re.match("[ =]", letter):
                    break
            
            fieldtype_start = line.index("models.") + len("models.")
            fieldtype = ""
            for letter in line[fieldtype_start:]:
                if re.match("\w",letter):
                    fieldtype += letter
                elif letter=="(":
                    break
            
            #if fieldtype == "ForeignKey" or fieldtype == "OneToOneField":
            # generate fk_def as a field definition for every type to use later
            fk_def = ""
            def_start = line.index("(") + 1
            for letter in line[def_start:]:
                if letter == ")":
                    break
                fk_def += letter
 
            fields_dict.append({"field_name": field_name, "type": fieldtype, "fk_def":fk_def})
            #else:
            #    fields_dict.append({"field_name": field_name, "type": fieldtype})
            
        elif re.match("^\s+db_table", line):
            table_name = line.split("=").pop().strip()
            table_name = re.sub(" .*","",table_name)
            
        elif len(views_start_kw) and re.match(f".*{views_start_kw}.*", line):
            include_view = line
    
    definition = {
        "table_name": table_name,
        "model_name": model_name,
        "fields": fields_dict,
        "intendation" : intent_type,
        "include_view": include_view,
    }
    return definition

                  
def generate_dbdiagram_code(definition, simple_view):
    """
    Generate diagram code syntax of definitions to be used on the website dbdiagram.io.
    Short example how it should look like of the Table definitions:
    
    Table {
        name type
    }
    """
    def get_field_type(key):
        """
        Django type to DBML type
        """
        fieldtype_translation = {
            "CharField":"varchar",
            "IntegerField": "integer",
            "DecimalField": "float",
            "SmallIntegerField": "smallinteger",
            "BooleanField": "boolean",
            "GeometryField": "geometry",
            "DateField": "date",
            "DateTimeField": "datetime",
            "TimeField": "time",
            "ForeignKey": "fk",
            "TextField": "text",
            "PolygonField": "polygon",
            "RasterField": "raster",
            "PointField": "point",
            "LineStringField": "linestring",
            "UUIDField": "uuid",
            "OneToOneField": "one-to-one",
            "BigIntegerField": "biginteger",
        }
        return fieldtype_translation[key]
        
        
    def parse_field_type_defs(type_def):
        """
        DBML syntax for settings of the field: only field length = "(len)" others: [ not null, unique etc]
        In the case of foreign key, it is not exact..Should be harmonized 
        input: django model field parameters: models.XxxxField(parameters)
        output: DBML field settings as string inside of "": name varchar "(234) [...]"
        """
        
        params = ('max_length','max_digits','null', 'blank','unique','default')
        
        type_string = ""
        list_of_constraints = type_def.split(",")
        #print(type_def)
        
        #if 'max_length'
        constraint_dict = {}
        for constraint in list_of_constraints:
            if "=" in constraint:
                c_key,c_value = constraint.strip().split("=")
                constraint_dict[c_key.strip()] = c_value.strip()
        
        if 'max_length' in constraint_dict.keys():
            type_string += f"({constraint_dict['max_length']})"
        elif 'max_digits' in constraint_dict.keys():
            type_string += f"({constraint_dict['max_digits']})"
        
        settings = []
        for param in params[1:]:
            if param in constraint_dict.keys() and param != "default" and constraint_dict[param] == "True":
                settings.append(param)
            elif param == "default" and param in constraint_dict.keys():
                sett = "default=" + constraint_dict[param]
                settings.append(sett)
        
        if len(settings)>0:
            type_string += f" [ {', '.join(settings)} ]"
        #        if c_key in params:
        #            if c_key == 'max_length':
        #                type_string += f"({c_value})"
        #            elif c_value.strip() == "True":
        #                type_string += f" {c_key}"
        #    else:
        #        print(constraint)
        return type_string
    
    #code = ""
    code = "Table "
    if not len(definition['table_name']):
        code += definition['model_name'].lower() + " {\n"
    else:
        # django models table name is like 'schema"."tablename' -> the bot ' and " should be removed from result
        code += re.sub(r"('|\")", '', definition['table_name']) + " {\n"

    foreignkey_list = []
    
    # in django this is default for all models and field is not included in the model
    if not re.match(".+[vV]ista.*" ,code):
        code += "  id integer [primary key]\n"
    

    for field in definition['fields']:
        if field['type'] != "ForeignKey" and field['type'] != "OneToOneField":
            field_type_def = ""
            if not simple_view:
                #list_of_defs = field['fk_def'].split(",")
                field_type_def = parse_field_type_defs(field['fk_def']) #+= field['fk_def']
            
            code += f"  {field['field_name']} {get_field_type(field['type'])}{field_type_def}\n"
        else:
            # add _id suffix to field names because django's default way in models.py is not using that
            code += f"  {field['field_name']}_id {get_field_type(field['type'])}\n"
    
    code += "}\n"
    
    code += definition['include_view'] + "\n"
    
    return code



def dict_filter(dictionary_list,lookup_key,value_list):
    """
    Looks for Pythond Dictionary with lookup_key where value is list
    """
    return [ dic for dic in dictionary_list if dic[lookup_key] in value_list ]
     

def search_references(definitions):
    """
    Search info from definitions of ForeignKey or one to one fields and models to generate dbdiagram syntax
    for describing table relationships. 
    
    """
    #def get_ref_model(fk_def):
    #references = []    
    model_fk_defs = []
    
    for model_def in definitions:
        # lookp up fk's from dict.fields: []
        
        # Debug
        #print("-------START---------")
        #print("MODEL: " + model_def['model_name'])
        #print("---------------")
        
        fk_list_of_model = dict_filter(model_def['fields'], 'type', ['ForeignKey','OneToOneField',])
        for fk_field in fk_list_of_model:
            
            # debug: ForeignKey fields
            #print(fk_field)
            
            fk_def_list = fk_field['fk_def'].split(",")
            override_model = None
            target_field = "id"
            for param in fk_def_list:
                if re.match("^to_field=.+$",param.strip()):
                    target_field = param.strip().split("=").pop()
                if re.match("^to='.+'$", param.strip()):
                    override_model = param.strip().split("=").pop()
                    
            fk_ref_model_name = None
            if not override_model:
                fk_ref_model_name = fk_def_list.pop(0).replace("'","")  # referenced model name of ForeignKey('xxx',to_field=yyy) where yyy = db_field, default = id
                # remove also "'" of name if exist
           
                if fk_ref_model_name == "self":
                    fk_ref_model_name = model_def['model_name']
                
            # find table name of the referenced model 
            
            # Debug
            # print(fk_ref_model_name)
            
            referenced_model = None
            table_name = ""
            # Django user table reference: default auth_user
            if fk_ref_model_name and fk_ref_model_name == 'User':
                table_name = 'tecomsg.auth_user'
            elif fk_ref_model_name:
                # look for table based on model_name
                referenced_model = dict_filter(definitions, 'model_name', [fk_ref_model_name])

                if referenced_model:
                    table_name = referenced_model[0]['table_name']
                
                if not len(table_name):
                    table_name = referenced_model[0]['model_name'].lower() # What is original schema, it is default, tecomsg, comun?
            else:
                table_name = override_model
                
            model_fk_defs.append({"source_table": model_def['table_name'].replace("'","").replace('"."','.'), 
                                    "field_name": fk_field['field_name'], 
                                    "reference_model": fk_ref_model_name, 
                                    "table_name": table_name.replace("'","").replace('"."','.'),
                                    "target_field": target_field})
     
    for ref_def in model_fk_defs:
        # at the moment there is no way how to say without checking the model which is one-to-many or many-to-many etc.
        # default is many to one
        print(f"Ref : {ref_def['source_table']}.{ref_def['field_name']}_id > {ref_def['table_name']}.{target_field} \n")
    return model_fk_defs

def commandline_exception(msg):
    print(msg)
    print("Usage: \n  gen_code_for_dbdiagamio.py  [-s] [-c views-tag] [--user[=User model table of django]] models-file\n")
    print("\tModels-file : Usually filename is 'models.py' found in Django's app directory\n")
    
    print("Options:")
    print("\t-c views-tag : The 'views-tag' are starting indicator for Django's view-models (begins with \"#\" \n\t\tfollowed by any characters) and they are not included in db structure. Use quotes\n\t\tif indicator has spaces, for example: -c \"# Views:\"")
    print("\t--user[=User model table of django] : Default user model teble is 'auth_user' in default schema.")
    print("\t-s : Simplify field definitions to show only type.")
    


# Debug: Number of models        
# print(len(list_of_definitions))
def main():
    # analyse and print every django model block
    data = None
    views_start_kw = "" 
    simple_view = False
    if '-s' in sys.argv:
        simple_view = True
    
    if len(sys.argv)>1 and os.path.isfile(sys.argv[-1]):
        filepath = sys.argv.pop()
        
        with open(filepath,'r') as file:
            data = file.read()
        
        views_start_kw = ""
        user_table = {'include':False,'table_name':'auth_user'}
        count = 0
        for arg in sys.argv:
            if re.match("^--user(=.+){0,1}$",arg):
                user_table['include'] = True
                if len(arg.split("=")) == 2:
                    user_table['table_name'] = arg.split("=").pop()
            
            
            elif arg == '-c' and len(sys.argv) > count+1 and re.match("^\s*#.+$", sys.argv[count+1] ):
                views_start_kw = sys.argv[count+1]
            
            count += 1
        
#        if len(sys.argv) == 3:
#            views_start_kw = sys.argv[-1]

        # print(views_start_kw)
        if len(data):
            lines = data.splitlines()

            list_of_classes = scan_main_blocks(lines, views_start_kw, user_table)

            list_of_definitions = []
            for dj_block in list_of_classes:
                definition = analyze_block(dj_block, views_start_kw)
                list_of_definitions.append(definition)
                code = generate_dbdiagram_code(definition, simple_view)    
                print(code)
        
            return search_references(list_of_definitions)
        else:
            commandline_exception("Models doesn't have any models. Check models.py and arguments")
    else:
        commandline_exception("Not enough arguments")   
        
if __name__ == '__main__':
    main()

