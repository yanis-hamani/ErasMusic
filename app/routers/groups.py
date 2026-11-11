from typing import Annotated

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Body, Depends, Path, Query, status

from app.core.openapi import (
    CONFLICT_RESPONSE,
    FORBIDDEN_RESPONSE,
    LIMIT_DESCRIPTION,
    NOT_FOUND_RESPONSE,
    PAGE_DESCRIPTION,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
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
    operation_id="listGroups",
    summary="Discover or list groups",
    description="Lists all groups available to authenticated users.",
    response_description="List of groups",
    responses={401: UNAUTHORIZED_RESPONSE, 422: VALIDATION_RESPONSE},
)
@inject
async def list_groups(
    group_service: FromDishka[GroupService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupsResponse:
    return await group_service.list_groups(page, limit)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=Group,
    operation_id="createGroup",
    summary="Create a group",
    description="Creates a group, its linked PostgreSQL chat, and an owner membership.",
    response_description="Group created",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
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
    operation_id="getGroup",
    summary="Get group details",
    description="Returns a group with its artist and genre tags.",
    response_description="Group details",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def get_group(
    groupId: Annotated[
        str,
        Path(description="Unique group identifier", examples=["grp_123"]),
    ],
    group_service: FromDishka[GroupService],
    _user_id: str = Depends(verify_access_token),
) -> Group:
    return await group_service.get_group(groupId)


@router.patch(
    "/{groupId}",
    response_model=Group,
    operation_id="updateGroup",
    summary="Update group details",
    description="Updates group metadata. Only the group owner can perform this action.",
    response_description="Group details updated",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def update_group(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    payload: GroupUpdate,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> Group:
    return await group_service.update_group(user_id, groupId, payload)


@router.delete(
    "/{groupId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteGroup",
    summary="Delete a group",
    description="Deletes a group and its linked PostgreSQL chat. Only the owner may delete it.",
    responses={
        204: {"description": "Group deleted"},
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
@inject
async def delete_group(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await group_service.delete_group(user_id, groupId)


@router.get(
    "/{groupId}/members",
    response_model=PaginatedGroupMembersResponse,
    operation_id="listGroupMembers",
    summary="List group members",
    description="Returns the group's owner and members with their roles and join dates.",
    response_description="Group members list",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def list_group_members(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    group_service: FromDishka[GroupService],
    page: int = Query(default=1, ge=1, description=PAGE_DESCRIPTION),
    limit: int = Query(default=10, ge=1, le=100, description=LIMIT_DESCRIPTION),
    _user_id: str = Depends(verify_access_token),
) -> PaginatedGroupMembersResponse:
    return await group_service.list_members(groupId, page, limit)


@router.post(
    "/{groupId}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=GroupMember,
    operation_id="addGroupMember",
    summary="Join a group or add a member",
    description=(
        "With no userId, the authenticated user joins the group. Adding another "
        "user is restricted to the group owner."
    ),
    response_description="Group membership created",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def add_group_member(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    group_service: FromDishka[GroupService],
    payload: GroupMemberCreate | None = Body(
        default=None,
        description="Omit userId to join as the authenticated user",
    ),
    user_id: str = Depends(verify_access_token),
) -> GroupMember:
    return await group_service.add_member(user_id, groupId, payload)


@router.delete(
    "/{groupId}/members/me",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="leaveGroup",
    summary="Leave a group",
    description="Members may leave; the owner must delete the group instead.",
    responses={
        204: {"description": "Current user left the group"},
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
@inject
async def leave_group(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> None:
    await group_service.leave_group(user_id, groupId)


@router.get(
    "/{groupId}/tags",
    response_model=list[GroupTag],
    operation_id="listGroupTags",
    summary="Get group tags",
    description="Returns the artist and genre tags attached to a group.",
    response_description="Group tags",
    responses={401: UNAUTHORIZED_RESPONSE, 404: NOT_FOUND_RESPONSE},
)
@inject
async def list_group_tags(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    group_service: FromDishka[GroupService],
    _user_id: str = Depends(verify_access_token),
) -> list[GroupTag]:
    return await group_service.list_tags(groupId)


@router.put(
    "/{groupId}/tags",
    response_model=list[GroupTag],
    operation_id="replaceGroupTags",
    summary="Replace group tags",
    description="Replaces every artist and genre tag. Only the group owner may do this.",
    response_description="Tags updated",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
    },
)
@inject
async def replace_group_tags(
    groupId: Annotated[str, Path(description="Unique group identifier")],
    payload: GroupTagsReplace,
    group_service: FromDishka[GroupService],
    user_id: str = Depends(verify_access_token),
) -> list[GroupTag]:
    return await group_service.replace_tags(user_id, groupId, payload)
