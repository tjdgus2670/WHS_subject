#include <stdio.h>
#include "json_c.c"

char *readFile(char *filename, int *readSize){
    FILE *fp;
    char *buffer;
    int size=0;
    int c;

    fp = fopen("ast.json", "r");

    if(fp == NULL){
        printf("파일열기 실패\n");
    } else {
        printf("파일열기 성공\n");
    }

    // 파일 크기 구하기
    fseek(fp, 0, SEEK_END);
    size = ftell(fp);
    fseek(fp, 0, SEEK_SET);

// 파일 크기 + NULL 공간만큼 메모리를 할당하고 0으로 초기화
    buffer = malloc(size + 1);
    memset(buffer, 0, size + 1);

    int count = 0;
    while((c = fgetc(fp)) != EOF){
        buffer[count] = (char)c;
        count++;
    }
    printf("%d \n", count);
    fclose(fp);
    return buffer;
}

//ext에서 FuncDef 노드의 인덱스를 찾아 arr에 저장하고, FuncDef 노드의 개수를 반환
int findFuncDef(json_value ext, int *arr) 
{
    int acnt = 0;
    int ext_len = json_len(ext);

    for(int i=0; i<ext_len; i++)
    {
        json_value ob = json_get(ext, i);

        if(ob.type == JSON_OBJECT)
        {
            char *id = json_get_string(ob, "_nodetype");

            if(id && strcmp(id, "FuncDef")==0)
            {
                arr[acnt++] = i;
            }
        }
    }

    return acnt;
}

//FuncDef 노드의 타입을 찾아 IdentifierType 노드까지 탐색
json_value findIdentifierType(json_value type)
{
    while (strcmp(json_get_string(type, "_nodetype"), "IdentifierType") != 0)
    {
        json_value next = json_get(type, "type");

        if(next.type == JSON_UNDEFINED)
            break;

        type = next;
    }
    return type;
}

//FuncDef 노드의 타입, 함수명, 파라미터 타입, 파라미터명을 출력
void printFunctionInfo(json_value ext, int index, int number)
{
    json_value func = json_get(ext, index);    
    json_value body = json_get(func, "body");

    json_value decl = json_get(func, "decl");
    json_value type = json_get(decl, "type");

    json_value type1 = findIdentifierType(type);

    json_value returnType = json_get(type1, "names");

    printf("%d회, 함수 번호 : %d\n", number, index);
    printf("리턴 타입 : %s\n", json_get_string(returnType, 0));
    printf("함수명 : %s\n\n", json_get_string(decl, "name"));

    printf("-------파라미터 타입과 파라미터명-----\n");
    printParameter(type);
    printf("--------------------------------------\n\n");

    printf("if 노드 개수 : %d\n", visit(ext, index, body));

    printf("\n");
}

//FuncDef 노드의 파라미터 타입과 파라미터명을 출력
void printParameter(json_value type)
{
    
    json_value args = json_get(type, "args");
    

    if (args.type != JSON_OBJECT)
    {
        printf("args 파라미터 없음\n");
        return;
    }

    json_value params = json_get(args, "params");
    
    //params는 배열이므로

    int len = json_len(params);

    for(int i = 0; i < len; i++)
    {
        json_value param = json_get(params, i);
        json_value type_par = json_get(param, "type");
        findIdentifierType(type_par);

        char *id = json_get_string(param, "_nodetype");
		char *name = json_get_string(param, "name");
		json_value identifierType = findIdentifierType(type_par);
        json_value returnType = json_get(identifierType, "names");

		printf("변수명: %s \n", name);
        printf("파라미터 타입: %s \n\n", json_get_string(returnType, 0));

    }
}

int visit(json_value ext, int index, json_value cur_node)
{
    int count = 0;
    json_value node = cur_node;

    // 1. If 체크
    if (cur_node.type == JSON_OBJECT)
    {
        char *nodetype = json_get_string(cur_node, "_nodetype");

        if (nodetype && strcmp(nodetype, "If") == 0)
        {
            count++;
        }
    }

    // 2. array 처리
    if (cur_node.type == JSON_ARRAY)
    {
        int len = json_len(cur_node);
        int child_count = 0;

        for (int i = 0; i < len; i++)
        {
            json_value next_if = json_get(cur_node, i);
            child_count += visit(ext, index, next_if);
        }
        return child_count;
    }

    // 3. object 내부 재귀 (핵심)
    if (cur_node.type == JSON_OBJECT)
    {
        // cur_node 안의 특정 필드들 계속 들어가기
        char *nodetype = json_get_string(cur_node, "_nodetype");

        if (nodetype && strcmp(nodetype, "Compound") == 0){
            node = json_get(cur_node, "block_items");
            count += visit(ext, index, node);
        }
        else if (nodetype && strcmp(nodetype, "While") == 0){
            json_value stmt = json_get(cur_node, "stmt");
            if(stmt.type == JSON_OBJECT){               
                count += visit(ext, index, stmt);
            }
        }
        else if (nodetype && strcmp(nodetype, "If") == 0){
            json_value iftrue = json_get(cur_node, "iftrue");
            json_value iffalse = json_get(cur_node, "iffalse");

            if(iftrue.type == JSON_OBJECT){               
                count += visit(ext, index, iftrue);
            }
            if(iffalse.type == JSON_OBJECT){               
                count += visit(ext, index, iffalse);
            }
        }
    }
    return count;
}



int main(void)
{
    char *fileContent = readFile("ast.json", NULL);

    if (fileContent == NULL)
        return 1;

    json_value json = json_create(fileContent);
    json_value ext = json_get(json, "ext");

    if (ext.type == JSON_UNDEFINED)
    {
        printf("에러 : ext를 찾을 수 없습니다.\n");
        return 1;
    }

    int ext_len = json_len(ext);
    int *arr = malloc(sizeof(int) * ext_len);
    int funcCount = findFuncDef(ext, arr);

    printf("FuncDef 개수 : %d\n\n", funcCount);

    for (int i = 0; i < funcCount; i++)
    {
        printFunctionInfo(ext, arr[i], i + 1);
    }

    free(arr);
    free(fileContent);

	return 0;
}

