from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, Query, status

from app.dependencies import verify_access_token
from app.models.groups import (
    Group,
    GroupCreate,
    GroupMember,
    GroupMemberCreate,
    GroupTag,
    GroupTagsReplace,
    GroupUpdate,
    PaginatedGroupMembersResponse,
    PaginatedGroupsResponse,
)
from app.services.group_services import GroupService


router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get(
    "",
    response_model=PaginatedGroupsResponse,
    responses={401: {"description": "Unauthorized"}},
)
@inject
async def list_groups(
    group_service: FromDishka[GroupService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupsResponse:
    return await group_service.list_groups(page, limit)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Group,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def create_group(
    payload: GroupCreate,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> Group:
    return await group_service.create_group(user_id, payload)


@router.get(
    "/{groupId}",
    response_model=Group,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def get_group(
    groupId: str,
    group_service: FromDishka[GroupService],
    _user_id: str = Depends(verify_access_token),
) -> Group:
    return await group_service.get_group(groupId)


@router.patch(
    "/{groupId}",
    response_model=Group,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
@inject
async def update_group(
    groupId: str,
    payload: GroupUpdate,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> Group:
    return await group_service.update_group(user_id, groupId, payload)


@router.delete(
    "/{groupId}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
@inject
async def delete_group(
    groupId: str,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await group_service.delete_group(user_id, groupId)


@router.get(
    "/{groupId}/members",
    response_model=PaginatedGroupMembersResponse,
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def list_group_members(
    groupId: str,
    group_service: FromDishka[GroupService],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupMembersResponse:
    return await group_service.list_members(groupId, page, limit)


@router.post(
    "/{groupId}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=GroupMember,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def add_group_member(
    groupId: str,
    group_service: FromDishka[GroupService],
    payload: GroupMemberCreate | None = Body(default=None),
    user_id: str = Depends(verify_access_token),
) -> GroupMember:
    return await group_service.add_member(user_id, groupId, payload)


@router.delete(
    "/{groupId}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not Found"},
        409: {"description": "Conflict"},
    },
)
@inject
async def leave_group(
    groupId: str,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await group_service.leave_group(user_id, groupId)


@router.get(
    "/{groupId}/tags",
    response_model=list[GroupTag],
    responses={401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}},
)
@inject
async def list_group_tags(
    groupId: str,
    group_service: FromDishka[GroupService],
    _user_id: str = Depends(verify_access_token),
) -> list[GroupTag]:
    return await group_service.list_tags(groupId)


@router.put(
    "/{groupId}/tags",
    response_model=list[GroupTag],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
)
@inject
async def replace_group_tags(
    groupId: str,
    payload: GroupTagsReplace,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> list[GroupTag]:
    return await group_service.replace_tags(user_id, groupId, payload)
